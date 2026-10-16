"""Private image notebook: bounded uploads and owner-scoped observations."""
import hashlib
import io
import json
import os
import secrets
import warnings
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel, Field
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select

from api.auth import current_user
from api.db import DATA_DIR, ImageRow, SessionLocal
from api.evidence import _object_store
from api.limits import rate_limit

router = APIRouter(prefix="/v1/images", tags=["images"])
MAX_BYTES = 15 * 1024 * 1024
TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class Mark(BaseModel):
    x: float = Field(ge=0, le=100)
    y: float = Field(ge=0, le=100)


class ImageNote(BaseModel):
    note: str = Field(max_length=2000)
    marks: list[Mark] = Field(max_length=100)


def _details(row: ImageRow) -> dict:
    return {"id": row.id, "filename": row.filename, "media_type": row.media_type,
            "sha256": row.sha256, "size_bytes": row.size_bytes, "width": row.width,
            "height": row.height, "note": row.note, "marks": json.loads(row.marks_json),
            "created_at": row.created_at, "image_url": f"/v1/images/{row.id}/file"}


def _owned(db, image_id: str, owner: str) -> ImageRow:
    row = db.get(ImageRow, image_id)
    if row is None or row.owner != owner:
        raise HTTPException(404, "Image not found")
    return row


@router.post("", status_code=201)
async def upload_image(request: Request, file: UploadFile = File(...), owner: str = Depends(current_user)):
    rate_limit(request, f"image-upload:{owner}", 10, 3600)
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES or not data:
        raise HTTPException(413, "Choose an image from 1 byte to 15 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                media_type = TYPES.get(image.format)
                width, height = image.size
                image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "The file is not a valid JPG, PNG, or WebP image") from exc
    if media_type is None or width > 12000 or height > 12000:
        raise HTTPException(422, "Use a JPG, PNG, or WebP image no larger than 12000 pixels per side")
    image_id = "img_" + secrets.token_hex(12)
    store = _object_store()
    if store:
        client, bucket = store
        try:
            client.put_object(Bucket=bucket, Key=f"images/{image_id}", Body=data, ContentType=media_type)
        except Exception as exc:
            raise HTTPException(503, "Image storage is unavailable") from exc
    else:
        folder = DATA_DIR / "images"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / image_id
        temporary = folder / f"{image_id}.part"
        temporary.write_bytes(data)
        os.replace(temporary, path)
    row = ImageRow(id=image_id, owner=owner, filename=Path(file.filename or "image").name[:180],
                   media_type=media_type, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                   width=width, height=height, note="", marks_json="[]",
                   created_at=datetime.now(timezone.utc).isoformat())
    try:
        with SessionLocal() as db:
            db.add(row)
            details = _details(row)
            db.commit()
    except Exception:
        # A failed metadata commit must not strand a private upload in storage.
        if store:
            try:
                client.delete_object(Bucket=bucket, Key=f"images/{image_id}")
            except Exception:
                pass
        else:
            (DATA_DIR / "images" / image_id).unlink(missing_ok=True)
        raise
    return details


@router.get("")
def list_images(owner: str = Depends(current_user)):
    with SessionLocal() as db:
        rows = db.scalars(select(ImageRow).where(ImageRow.owner == owner)
                          .order_by(ImageRow.created_at.desc()).limit(50)).all()
        return {"images": [_details(row) for row in rows]}


@router.get("/{image_id}")
def read_image(image_id: str, owner: str = Depends(current_user)):
    with SessionLocal() as db:
        return _details(_owned(db, image_id, owner))


@router.get("/{image_id}/file")
def image_file(image_id: str, owner: str = Depends(current_user)):
    with SessionLocal() as db:
        row = _owned(db, image_id, owner)
        digest, media_type = row.sha256, row.media_type
    store = _object_store()
    if store:
        client, bucket = store
        try:
            data = client.get_object(Bucket=bucket, Key=f"images/{image_id}")["Body"].read()
        except Exception as exc:
            raise HTTPException(503, "Image storage is unavailable") from exc
    else:
        try:
            data = (DATA_DIR / "images" / image_id).read_bytes()
        except FileNotFoundError as exc:
            raise HTTPException(404, "Image file is missing") from exc
    if hashlib.sha256(data).hexdigest() != digest:
        raise HTTPException(409, "Image failed checksum verification")
    return Response(data, media_type=media_type, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"})


@router.put("/{image_id}")
def save_image_note(image_id: str, body: ImageNote, owner: str = Depends(current_user)):
    with SessionLocal() as db:
        row = _owned(db, image_id, owner)
        row.note = body.note.strip()
        row.marks_json = json.dumps([mark.model_dump() for mark in body.marks])
        db.commit()
        return _details(row)
