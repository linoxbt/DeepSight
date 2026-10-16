"""Database-backed fixed-window budgets for costly public operations."""
import hashlib
import ipaddress
import os
import time

from fastapi import HTTPException, Request
from sqlalchemy import text

from api.db import SessionLocal


def client_identity(request: Request) -> str:
    peer = request.client.host if request.client else "unknown"
    trusted = os.environ.get("DEEPSIGHT_TRUSTED_PROXY_CIDRS", "")
    try:
        address = ipaddress.ip_address(peer)
        networks = [ipaddress.ip_network(item.strip(), strict=False) for item in trusted.split(",") if item.strip()]
        if not any(address in network for network in networks):
            return peer
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        return str(ipaddress.ip_address(forwarded)) if forwarded else peer
    except ValueError:
        return peer


def rate_limit(request: Request, scope: str, limit: int, window_seconds: int = 300, *, global_scope: bool = False) -> None:
    now = int(time.time())
    window = now // window_seconds
    client = "all-clients" if global_scope else client_identity(request)
    key = hashlib.sha256(f"{scope}:{client}:{window}".encode()).hexdigest()
    expires = (window + 1) * window_seconds
    with SessionLocal() as db:
        db.execute(text("DELETE FROM rate_limits WHERE expires < :now"), {"now": now})
        db.execute(text("INSERT INTO rate_limits (key, count, expires) VALUES (:key, 0, :expires) ON CONFLICT (key) DO NOTHING"), {"key": key, "expires": expires})
        changed = db.execute(text("UPDATE rate_limits SET count = count + 1 WHERE key = :key AND count < :limit"), {"key": key, "limit": limit})
        db.commit()
    if changed.rowcount != 1:
        raise HTTPException(429, "Request budget reached; retry after the window ends", headers={"Retry-After": str(max(1, expires - now))})
