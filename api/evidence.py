"""Immutable content-addressed evidence, backed up with the application database."""
import hashlib
import importlib.metadata
import json
import platform
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from api.db import ArtifactOwnerRow, ArtifactRow, SessionLocal
from api.auth import current_user

router = APIRouter(prefix="/v1", tags=["evidence"])


def put_json(document: dict, owner: str | None = None) -> str:
    content = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    digest = hashlib.sha256(content.encode()).hexdigest()
    with SessionLocal() as db:
        # Concurrent writers may insert the same content. Insert the grant only
        # after the artifact insert has settled so a duplicate never loses access.
        if db.get(ArtifactRow, digest) is None:
            db.add(ArtifactRow(digest=digest, content=content, public=owner is None))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
        if owner and db.scalar(select(ArtifactOwnerRow).where(ArtifactOwnerRow.digest == digest, ArtifactOwnerRow.owner == owner)) is None:
            db.add(ArtifactOwnerRow(digest=digest, owner=owner))
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
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


def publish_manifest(db, manifest: dict) -> None:
    refs = list(manifest.get("artifacts", [])) + list(manifest.get("cross_matches", []))
    refs.append({"sha256": manifest.get("analysis", {}).get("environment_sha256")})
    for ref in refs:
        digest = ref.get("sha256") or ref.get("query_snapshot_sha256")
        if digest:
            row = db.get(ArtifactRow, digest)
            if row is not None:
                row.public = True


@router.get("/artifacts/{digest}")
def artifact(digest: str, request: Request):
    with SessionLocal() as db:
        row = db.get(ArtifactRow, digest)
        if row is None:
            raise HTTPException(404, "Evidence artifact not found")
        if not row.public:
            user = current_user(request)
            grant = db.scalar(select(ArtifactOwnerRow).where(ArtifactOwnerRow.digest == digest, ArtifactOwnerRow.owner == user))
            if grant is None:
                raise HTTPException(404, "Evidence artifact not found")
    return Response(read(digest), media_type="application/json", headers={
        "ETag": f'"{digest}"', "Cache-Control": "public, max-age=31536000, immutable" if row.public else "private, no-store",
        "Content-Disposition": f'attachment; filename="{digest}.json"',
    })
