import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.limits import client_identity, rate_limit


def test_queue_rejects_global_worker_saturation():
    import time
    from fastapi.testclient import TestClient
    from api.db import JobRow, SessionLocal
    from api.main import app
    with SessionLocal() as db:
        for index in range(8):
            db.add(JobRow(id=f"job_busy_{index}", owner=f"0x{index:040x}", kind="analysis",
                          payload="{}", status="running", created=int(time.time()), updated=int(time.time())))
        db.commit()
    with TestClient(app) as client:
        response = client.post("/v1/jobs", json={"kind": "analysis", "target_id": "DS-SYN-001"})
        assert response.status_code == 503
        assert "busy" in response.json()["detail"]


def _request(address: str, forwarded: str = "") -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "method": "GET", "path": "/", "client": (address, 1234), "headers": headers})


def test_forwarded_ip_requires_trusted_peer(monkeypatch):
    monkeypatch.setenv("DEEPSIGHT_TRUSTED_PROXY_CIDRS", "10.0.0.0/8")
    assert client_identity(_request("192.0.2.4", "198.51.100.9")) == "192.0.2.4"
    assert client_identity(_request("10.0.0.5", "198.51.100.9")) == "198.51.100.9"


def test_global_budget_is_shared_across_source_ips():
    rate_limit(_request("192.0.2.4"), "shared-test", 1, 3600, global_scope=True)
    with pytest.raises(HTTPException) as error:
        rate_limit(_request("198.51.100.9"), "shared-test", 1, 3600, global_scope=True)
    assert error.value.status_code == 429
