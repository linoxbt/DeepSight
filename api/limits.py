"""Database-backed fixed-window budgets for costly public operations."""
import hashlib
import time

from fastapi import HTTPException, Request
from sqlalchemy import text

from api.db import SessionLocal


def rate_limit(request: Request, scope: str, limit: int, window_seconds: int = 300) -> None:
    now = int(time.time())
    window = now // window_seconds
    client = request.client.host if request.client else "unknown"
    key = hashlib.sha256(f"{scope}:{client}:{window}".encode()).hexdigest()
    expires = (window + 1) * window_seconds
    with SessionLocal() as db:
        db.execute(text("DELETE FROM rate_limits WHERE expires < :now"), {"now": now})
        db.execute(text("INSERT INTO rate_limits (key, count, expires) VALUES (:key, 0, :expires) ON CONFLICT (key) DO NOTHING"), {"key": key, "expires": expires})
        changed = db.execute(text("UPDATE rate_limits SET count = count + 1 WHERE key = :key AND count < :limit"), {"key": key, "limit": limit})
        db.commit()
    if changed.rowcount != 1:
        raise HTTPException(429, "Request budget reached; retry after the window ends", headers={"Retry-After": str(max(1, expires - now))})
