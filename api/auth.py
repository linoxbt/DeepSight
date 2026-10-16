"""Wallet proof sessions. Nonces are one-use; bearer secrets never enter the DB."""
import hashlib
import os
import secrets
import time
from urllib.parse import urlparse

from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, func

from api.db import AuthChallenge, AuthSession, SessionLocal
from api.limits import rate_limit

router = APIRouter(prefix="/v1/auth", tags=["identity"])
COOKIE = "deepsight_session"


def origin() -> str:
    return os.environ.get("DEEPSIGHT_ORIGIN", "http://localhost:3000").rstrip("/")


def check_origin(request: Request) -> None:
    supplied = request.headers.get("origin")
    if supplied and supplied != origin():
        raise HTTPException(403, "Request origin is not allowed")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Cross-site writes are not allowed")


def current_user(request: Request) -> str:
    if request.method not in ("GET", "HEAD"):
        check_origin(request)
    token = request.cookies.get(COOKIE, "")
    with SessionLocal() as db:
        session = db.get(AuthSession, hashlib.sha256(token.encode()).hexdigest())
        if not session or session.expires <= int(time.time()):
            raise HTTPException(401, "Sign in with your wallet to continue")
        return session.address


def require_owner(claim, user: str) -> None:
    if not claim.owner or claim.owner != user:
        raise HTTPException(403, "Only the authenticated claimant can change this claim")


def require_reviewer(user: str) -> None:
    reviewers = {v.strip().lower() for v in os.environ.get("DEEPSIGHT_REVIEWERS", "").split(",") if v.strip()}
    if user not in reviewers:
        raise HTTPException(403, "A designated reviewer account is required")


class ChallengeIn(BaseModel):
    address: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")


class VerifyIn(BaseModel):
    challenge_id: str = Field(min_length=32, max_length=64)
    signature: str = Field(pattern=r"^(0x)?[0-9a-fA-F]{130}$")


@router.post("/challenge")
def challenge(body: ChallengeIn, request: Request):
    check_origin(request)
    rate_limit(request, "auth-challenge", 30)
    now = int(time.time())
    nonce = secrets.token_hex(24)
    address = body.address.lower()
    message = (f"{urlparse(origin()).netloc} requests a DeepSight sign-in.\n"
               f"Wallet: {address}\nURI: {origin()}\nNonce: {nonce}\n"
               f"Issued at: {now}\nExpires at: {now + 300}\n"
               "This signature creates a research session. It does not authorize a blockchain transaction.")
    with SessionLocal() as db:
        db.execute(delete(AuthChallenge).where(AuthChallenge.expires < now))
        db.execute(delete(AuthSession).where(AuthSession.expires < now))
        active = db.scalar(select(func.count()).select_from(AuthChallenge).where(AuthChallenge.address == address))
        if active >= 5:
            raise HTTPException(429, "Too many sign-in challenges; wait five minutes")
        db.add(AuthChallenge(id=nonce, address=address, message=message, expires=now + 300))
        db.commit()
    return {"id": nonce, "message": message}


@router.post("/session")
def verify(body: VerifyIn, request: Request, response: Response):
    check_origin(request)
    now = int(time.time())
    with SessionLocal() as db:
        row = db.get(AuthChallenge, body.challenge_id)
        if row is None or row.expires <= now:
            raise HTTPException(401, "Sign-in challenge expired or already used")
        try:
            address = Account.recover_message(encode_defunct(text=row.message), signature=body.signature).lower()
        except Exception as exc:
            raise HTTPException(401, "Invalid signature") from exc
        if address != row.address:
            raise HTTPException(401, "Signature does not match this wallet")
        consumed = db.execute(delete(AuthChallenge).where(AuthChallenge.id == row.id, AuthChallenge.expires > now))
        if consumed.rowcount != 1:
            raise HTTPException(401, "Challenge already used")
        token = secrets.token_urlsafe(32)
        db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), address=address, expires=now + 28800))
        db.commit()
    response.set_cookie(COOKIE, token, httponly=True, secure=origin().startswith("https://"), samesite="strict", max_age=28800, path="/")
    return {"address": address}


@router.get("/session")
def session(user: str = Depends(current_user)):
    return {"address": user}


@router.delete("/session")
def logout(request: Request, response: Response):
    check_origin(request)
    digest = hashlib.sha256(request.cookies.get(COOKIE, "").encode()).hexdigest()
    with SessionLocal() as db:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == digest))
        db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"signed_out": True}
