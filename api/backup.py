"""Daily, checksum-verified copies of evidence objects to isolated storage."""

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import boto3

MAX_OBJECT_BYTES = 100 * 1024 * 1024
MAX_DATABASE_BYTES = 1024 * 1024 * 1024


def _client(bucket_prefix: str):
    if bucket_prefix == "DEEPSIGHT_S3":
        return boto3.client("s3", endpoint_url=os.environ["DEEPSIGHT_S3_ENDPOINT"]), os.environ["DEEPSIGHT_S3_BUCKET"]
    return boto3.client(
        "s3",
        endpoint_url=os.environ[f"{bucket_prefix}_ENDPOINT"],
        aws_access_key_id=os.environ[f"{bucket_prefix}_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ[f"{bucket_prefix}_SECRET_ACCESS_KEY"],
    ), os.environ[f"{bucket_prefix}_BUCKET"]


def configured() -> bool:
    required = ["DEEPSIGHT_S3_ENDPOINT", "DEEPSIGHT_S3_BUCKET", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
    required += [f"DEEPSIGHT_BACKUP_{field}" for field in
                 ("ENDPOINT", "ACCESS_KEY_ID", "SECRET_ACCESS_KEY", "BUCKET")]
    return all(os.environ.get(name) for name in required)


def snapshot(day: str | None = None) -> dict:
    """Complete a dated snapshot; publish its manifest only after all copies verify."""
    if not configured():
        raise RuntimeError("Source or backup bucket is not configured")
    day = day or datetime.now(timezone.utc).date().isoformat()
    source, source_bucket = _client("DEEPSIGHT_S3")
    backup, backup_bucket = _client("DEEPSIGHT_BACKUP")
    if source_bucket == backup_bucket:
        raise RuntimeError("Recovery bucket must differ from the live bucket")
    prefix = f"snapshots/{day}/"
    marker = prefix + "manifest.json"
    rows = []
    for page in source.get_paginator("list_objects_v2").paginate(Bucket=source_bucket):
        for item in page.get("Contents", []):
            key = item["Key"]
            if item["Size"] > MAX_OBJECT_BYTES:
                raise RuntimeError(f"Evidence object exceeds backup limit: {key}")
            content = source.get_object(Bucket=source_bucket, Key=key)["Body"].read(MAX_OBJECT_BYTES + 1)
            if len(content) > MAX_OBJECT_BYTES:
                raise RuntimeError(f"Evidence object exceeds backup limit: {key}")
            digest = hashlib.sha256(content).hexdigest()
            backup.put_object(Bucket=backup_bucket, Key=prefix + key, Body=content,
                              Metadata={"sha256": digest})
            recovered = backup.get_object(Bucket=backup_bucket, Key=prefix + key)["Body"].read()
            if hashlib.sha256(recovered).hexdigest() != digest:
                raise RuntimeError(f"Recovery object failed checksum: {key}")
            rows.append({"key": key, "sha256": digest, "bytes": len(content)})
    rows.sort(key=lambda item: item["key"])
    manifest = {"date": day, "objects": rows}
    backup.put_object(Bucket=backup_bucket, Key=marker,
                      Body=json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode(),
                      ContentType="application/json")
    return {"date": day, "objects": len(rows), "bytes": sum(item["bytes"] for item in rows)}


def database_snapshot(day: str | None = None) -> dict:
    """Save a consistent PostgreSQL custom-format dump outside the live bucket."""
    if not configured():
        raise RuntimeError("Recovery bucket is not configured")
    raw_url = os.environ.get("DATABASE_URL", "")
    parsed = urlsplit(raw_url)
    if parsed.scheme not in ("postgresql", "postgres") or not parsed.hostname or not parsed.path.strip("/"):
        raise RuntimeError("PostgreSQL DATABASE_URL is required for a database snapshot")
    day = day or datetime.now(timezone.utc).date().isoformat()
    username = parsed.username or ""
    host = parsed.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    authority = (username + "@" if username else "") + host + (f":{parsed.port}" if parsed.port else "")
    safe_url = urlunsplit((parsed.scheme, authority, parsed.path, parsed.query, ""))
    environment = os.environ.copy()
    environment["PGPASSWORD"] = unquote(parsed.password or "")
    backup, bucket = _client("DEEPSIGHT_BACKUP")
    key = f"database/{day}.dump"
    with tempfile.TemporaryDirectory(prefix="deepsight-db-backup-") as directory:
        path = Path(directory) / "database.dump"
        try:
            completed = subprocess.run(
                ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(path), safe_url],
                env=environment, capture_output=True, timeout=300, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("PostgreSQL dump could not complete") from exc
        if completed.returncode != 0 or not path.is_file():
            raise RuntimeError("PostgreSQL dump failed; recovery marker was not written")
        size = path.stat().st_size
        if not 0 < size <= MAX_DATABASE_BYTES:
            raise RuntimeError("PostgreSQL dump is empty or exceeds the backup limit")
        with path.open("rb") as stream:
            if stream.read(5) != b"PGDMP":
                raise RuntimeError("PostgreSQL dump has an invalid custom-format header")
        digest = _file_sha256(path)
        with path.open("rb") as stream:
            backup.upload_fileobj(stream, bucket, key, ExtraArgs={"Metadata": {"sha256": digest}})
        remote_digest = hashlib.sha256()
        body = backup.get_object(Bucket=bucket, Key=key)["Body"]
        try:
            while chunk := body.read(1024 * 1024):
                remote_digest.update(chunk)
        finally:
            body.close()
        if remote_digest.hexdigest() != digest:
            raise RuntimeError("Database recovery dump failed checksum")
        manifest = {"date": day, "key": key, "sha256": digest, "bytes": size, "format": "pg_dump-custom"}
        backup.put_object(Bucket=bucket, Key=f"database/{day}.manifest.json",
                          Body=json.dumps(manifest, sort_keys=True).encode(), ContentType="application/json")
        return manifest


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
