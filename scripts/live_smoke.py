"""Exercise a running local web proxy, API, worker, and real archives over HTTP.

Run with DEEPSIGHT_SMOKE_BASE=http://127.0.0.1:3300. The smoke test creates a
temporary research wallet and writes a dataset, analysis, and local claim.
"""

from __future__ import annotations

import os
import time
from urllib.parse import urlparse

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct


BASE = os.environ.get("DEEPSIGHT_SMOKE_BASE", "http://127.0.0.1:3300").rstrip("/")
if urlparse(BASE).hostname not in {"localhost", "127.0.0.1", "::1"}:
    raise SystemExit("The smoke test writes data. Use a loopback URL only.")


def main() -> None:
    wallet = Account.create()
    with httpx.Client(base_url=BASE, headers={"Origin": BASE}, timeout=120) as client:
        def call(method: str, path: str, body: dict | None = None) -> dict:
            response = client.request(method, path, json=body)
            if response.status_code >= 400:
                raise RuntimeError(f"{method} {path}: HTTP {response.status_code}: {response.text[:300]}")
            print(f"PASS {method} {path} ({response.status_code})", flush=True)
            return response.json()

        for path in ("/v1/health", "/v1/sources", "/v1/catalogue", "/v1/targets",
                     "/v1/claims", "/v1/discoveries", "/v1/reviews", "/v1/chain/config"):
            call("GET", path)
        if client.get("/v1/auth/session").status_code != 401:
            raise RuntimeError("Unauthenticated session was accepted")
        challenge = call("POST", "/v1/auth/challenge", {"address": wallet.address})
        signature = Account.sign_message(encode_defunct(text=challenge["message"]), wallet.key).signature.hex()
        call("POST", "/v1/auth/session", {"challenge_id": challenge["id"], "signature": signature})
        if call("GET", "/v1/auth/session")["address"] != wallet.address.lower():
            raise RuntimeError("Wallet session address mismatch")

        # These calls reach the real NASA, ESA, and JPL services through the API.
        tap = call("POST", "/v1/archives/tap", {"tic": "259377017"})
        if not tap.get("rows"):
            raise RuntimeError("NASA TAP returned no rows for the known example")
        gaia = call("POST", "/v1/archives/gaia", {"ra_deg": 63.445833, "dec_deg": -26.999722})
        if not gaia.get("sources") and not gaia.get("rows"):
            raise RuntimeError("Gaia returned no nearby sources")
        horizons = call("POST", "/v1/archives/horizons", {"command": "499"})
        if not horizons:
            raise RuntimeError("JPL Horizons returned an empty response")
        radio_catalog = call("POST", "/v1/radio/catalog", {"target": "VOYAGER1"})
        if not radio_catalog.get("observations"):
            raise RuntimeError("Breakthrough Listen returned no Voyager rows")

        def job(kind: str, **fields: str) -> dict:
            queued = call("POST", "/v1/jobs", {"kind": kind, **fields})
            for _ in range(120):
                state = call("GET", f"/v1/jobs/{queued['id']}")
                if state["status"] == "succeeded":
                    return state["result"]
                if state["status"] == "failed":
                    raise RuntimeError(f"{kind} job failed: {state['error']}")
                time.sleep(2)
            raise RuntimeError(f"{kind} job did not complete within four minutes")

        imported = job("import", tic="259377017")
        target_id = imported["target"]["id"]
        if target_id != "TIC-259377017":
            raise RuntimeError(f"MAST returned unexpected target: {target_id}")
        analysis = job("analysis", target_id=target_id)
        analysis_id = analysis["id"]
        call("GET", f"/v1/analyses/{analysis_id}")
        call("POST", "/v1/evidence/preflight", {"analysis_id": analysis_id})
        claim = call("POST", "/v1/claims", {"analysis_id": analysis_id, "acknowledged": True})
        claim_id = claim["id"]
        for path in (f"/v1/claims/{claim_id}", f"/v1/claims/{claim_id}/manifest",
                     f"/v1/claims/{claim_id}/timeline", f"/v1/claims/{claim_id}/policy-result",
                     f"/v1/claims/{claim_id}/finality", f"/v1/claims/{claim_id}/bundle", "/v1/jobs"):
            call("GET", path)
        radio = job("radio")
        call("GET", f"/v1/radio/analyses/{radio['id']}")
        radio_claim = call("POST", "/v1/radio/claims", {"analysis_id": radio["id"], "acknowledged": True})
        call("GET", f"/v1/claims/{radio_claim['id']}/manifest")
        call("DELETE", "/v1/auth/session")
        if client.get("/v1/auth/session").status_code != 401:
            raise RuntimeError("Logout did not revoke the session")
        print(f"LIVE_SMOKE_PASS target={target_id} analysis={analysis_id} claim={claim_id} radio={radio['id']}", flush=True)


if __name__ == "__main__":
    main()
