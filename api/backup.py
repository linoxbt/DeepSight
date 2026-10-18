"""Daily, checksum-verified copies of evidence objects to isolated storage."""

import hashlib
import json
import os
from datetime import datetime, timezone

import boto3

MAX_OBJECT_BYTES = 100 * 1024 * 1024


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
