import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from api import backup


class Bucket:
    def __init__(self, objects=None, corrupt=False):
        self.objects = dict(objects or {})
        self.corrupt = corrupt

    def get_paginator(self, _name):
        return self

    def paginate(self, **_kwargs):
        yield {"Contents": [{"Key": key, "Size": len(value)} for key, value in self.objects.items()]}

    def get_object(self, *, Key, **_kwargs):
        body = self.objects[Key]
        if self.corrupt and Key.endswith("curve.json"):
            body += b"tampered"
        return {"Body": io.BytesIO(body)}

    def put_object(self, *, Key, Body, **_kwargs):
        self.objects[Key] = Body

    def upload_fileobj(self, stream, _bucket, key, **_kwargs):
        self.objects[key] = stream.read()


def test_snapshot_copies_and_verifies_before_publishing_manifest(monkeypatch):
    source = Bucket({"artifacts/curve.json": b"curve"})
    destination = Bucket()
    monkeypatch.setattr(backup, "configured", lambda: True)
    monkeypatch.setattr(backup, "_client", lambda prefix: (source, "live") if prefix == "DEEPSIGHT_S3" else (destination, "recovery"))
    result = backup.snapshot("2026-10-18")
    assert result == {"date": "2026-10-18", "objects": 1, "bytes": 5}
    manifest = json.loads(destination.objects["snapshots/2026-10-18/manifest.json"])
    assert manifest["objects"][0]["sha256"] == hashlib.sha256(b"curve").hexdigest()
    assert destination.objects["snapshots/2026-10-18/artifacts/curve.json"] == b"curve"


def test_corrupt_backup_never_gets_completion_marker(monkeypatch):
    source = Bucket({"artifacts/curve.json": b"curve"})
    destination = Bucket(corrupt=True)
    monkeypatch.setattr(backup, "configured", lambda: True)
    monkeypatch.setattr(backup, "_client", lambda prefix: (source, "live") if prefix == "DEEPSIGHT_S3" else (destination, "recovery"))
    with pytest.raises(RuntimeError, match="failed checksum"):
        backup.snapshot("2026-10-18")
    assert "snapshots/2026-10-18/manifest.json" not in destination.objects


def test_database_dump_is_verified_and_password_is_not_in_command(monkeypatch):
    destination = Bucket()
    monkeypatch.setattr(backup, "configured", lambda: True)
    monkeypatch.setattr(backup, "_client", lambda _prefix: (destination, "recovery"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://researcher:s%40cret@db.example:5432/deepsight?sslmode=require")

    def dump(command, *, env, **_kwargs):
        assert env["PGPASSWORD"] == "s@cret"
        assert "s%40cret" not in " ".join(command)
        assert "sslmode=require" in command[-1]
        Path(command[command.index("--file") + 1]).write_bytes(b"PGDMPtest")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(backup.subprocess, "run", dump)
    result = backup.database_snapshot("2026-10-18")
    assert result["sha256"] == hashlib.sha256(b"PGDMPtest").hexdigest()
    assert destination.objects["database/2026-10-18.dump"] == b"PGDMPtest"
    assert json.loads(destination.objects["database/2026-10-18.manifest.json"])["format"] == "pg_dump-custom"


def test_failed_database_dump_has_no_completion_marker(monkeypatch):
    destination = Bucket()
    monkeypatch.setattr(backup, "configured", lambda: True)
    monkeypatch.setattr(backup, "_client", lambda _prefix: (destination, "recovery"))
    monkeypatch.setenv("DATABASE_URL", "postgresql://researcher:secret@db.example/deepsight")
    monkeypatch.setattr(backup.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(returncode=1))
    with pytest.raises(RuntimeError, match="dump failed"):
        backup.database_snapshot("2026-10-18")
    assert "database/2026-10-18.manifest.json" not in destination.objects
