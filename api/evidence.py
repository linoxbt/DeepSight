"""Immutable content-addressed evidence, backed up with the application database."""
import hashlib
import importlib.metadata
import json
import platform
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy.exc import IntegrityError

from api.db import ArtifactRow, SessionLocal

router = APIRouter(prefix="/v1", tags=["evidence"])


def put_json(document: dict) -> str:
    content = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    digest = hashlib.sha256(content.encode()).hexdigest()
    with SessionLocal() as db:
        if db.get(ArtifactRow, digest) is None:
            db.add(ArtifactRow(digest=digest, content=content))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()  # Concurrent writers of identical content are idempotent.
    return digest


def read(digest: str) -> str:
    with SessionLocal() as db:
        row = db.get(ArtifactRow, digest)
        if row is None:
            raise HTTPException(404, "Evidence artifact not found; legacy analyses must be rerun")
        content = row.content
    if hashlib.sha256(content.encode()).hexdigest() != digest:
        raise HTTPException(409, "Stored evidence failed checksum verification")
    return content


@lru_cache(maxsize=1)
def environment() -> dict:
    root = Path(__file__).resolve().parent
    source = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.glob("*.py"))}
    packages = {name: importlib.metadata.version(name) for name in ("numpy", "astropy", "fastapi", "sqlalchemy")}
    return {"python": platform.python_version(), "packages": packages, "source_checksums": source, "source_files": {p.name: p.read_text() for p in sorted(root.glob("*.py"))}}


@router.get("/artifacts/{digest}")
def artifact(digest: str):
    return Response(read(digest), media_type="application/json", headers={
        "ETag": f'"{digest}"', "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": f'attachment; filename="{digest}.json"',
    })
