import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.limits import client_identity, rate_limit


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
