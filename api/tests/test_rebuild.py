import ast
import hashlib
import json
import time
from pathlib import Path

import pytest
from eth_account import Account
from eth_account.messages import encode_defunct
from astropy.io import fits
from fastapi.testclient import TestClient
from sqlalchemy import select

from api import chain_ops, evidence, jobs
from api.auth import current_user, optional_user
from api.db import DATA_DIR, AuthSession, ClaimRow, ChainIntent, ChainOperation, SessionLocal
from api.main import app
from api.policy import evaluate
from api.tests.test_policy import _base

OWNER = "0x" + "1" * 40
OTHER = "0x" + "2" * 40


def insert_claim(status="EVIDENCE_READY", owner=OWNER):
    document = _base()
    # Existing outbox fixtures represent claims pinned to the deployed v4
    # contract; new v5 behavior has its own version-specific tests.
    document["policy_version"] = "celestial-v4"
    document["claimant_address"] = owner
    document["researcher_address"] = owner
    digest = evidence.put_json({"time_days": [0, 1], "flux": [1, 1]})
    document["artifacts"] = [{"sha256": digest, "uri": f"/v1/artifacts/{digest}"}]
    document["analysis"]["environment_sha256"] = evidence.put_json({"environment": "test"})
    document["cross_matches"][0]["query_snapshot_sha256"] = evidence.put_json({"catalogue": "test"})
    raw_path = DATA_DIR / "test_raw.fits"
    fits.HDUList([fits.PrimaryHDU()]).writeto(raw_path, overwrite=True)
    raw_digest = evidence.put_fits(raw_path)
    document["archive"]["raw_source_sha256"] = raw_digest
    document["archive"]["raw_source_uri"] = f"/v1/raw/{raw_digest}"
    text = json.dumps(document)
    with SessionLocal() as db:
        row = ClaimRow(id="clm_test", analysis_id="an_test", owner=owner, manifest_json=text,
                       manifest_hash=hashlib.sha256(text.encode()).hexdigest(), status=status,
                       created_at="now", updated_at="now")
        db.add(row); db.commit()
    return "clm_test"


def test_wallet_session_requires_signature_and_nonce_is_single_use():
    app.dependency_overrides.clear()
    wallet = Account.create()
    with TestClient(app) as client:
        assert client.post("/v1/analyses", json={"target_id": "DS-SYN-001"}).status_code == 401
        challenge = client.post("/v1/auth/challenge", json={"address": wallet.address}).json()
        signed = Account.sign_message(encode_defunct(text=challenge["message"]), wallet.key)
        body = {"challenge_id": challenge["id"], "signature": signed.signature.hex()}
        response = client.post("/v1/auth/session", json=body)
        assert response.status_code == 200
        assert "HttpOnly" in response.headers["set-cookie"]
        assert client.get("/v1/auth/session").json()["address"] == wallet.address.lower()
        assert client.post("/v1/auth/session", json=body).status_code == 401
        assert client.delete("/v1/auth/session", headers={"origin": "https://attacker.invalid"}).status_code == 403
        assert client.delete("/v1/auth/session").status_code == 200
        assert client.get("/v1/auth/session").status_code == 401


def test_studionet_deployment_is_discoverable_without_local_chain_file(monkeypatch):
    from api.chain import load_config
    monkeypatch.delenv("DEEPSIGHT_IGNORE_CHAIN_FILE", raising=False)
    monkeypatch.delenv("DEEPSIGHT_CONTRACT_ADDRESS", raising=False)
    config = load_config()
    assert config is not None
    assert config["address"] == "0x10852d994e4a96592EdF464BDfB42ED2A3819451"
    old = type("Claim", (), {"manifest_json": json.dumps({"policy_version": "celestial-v4"})})()
    assert chain_ops.config_for_claim(old)["address"] == "0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1"
    current = type("Claim", (), {"manifest_json": json.dumps({"policy_version": "celestial-v5"})})()
    assert chain_ops.config_for_claim(current)["address"] == config["address"]


def test_packaged_source_revision_is_verifiable_without_git(monkeypatch):
    from api.main import _git_commit
    monkeypatch.delenv("DEEPSIGHT_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setattr("api.main.subprocess.check_output", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    revision = _git_commit()
    assert revision.startswith("source-sha256:") and len(revision) == 78


def test_public_release_identity_matches_running_source_without_secrets(monkeypatch):
    monkeypatch.delenv("DEEPSIGHT_GIT_COMMIT", raising=False)
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.setattr("api.main.subprocess.check_output", lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()))
    monkeypatch.setattr("api.main.chain.load_config", lambda: {"address": "0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1"})
    with TestClient(app) as client:
        response = client.get("/v1/release")
    assert response.status_code == 200
    identity = response.json()
    expected = hashlib.sha256(json.dumps(evidence.environment()["source_checksums"], sort_keys=True).encode()).hexdigest()
    assert identity["source_sha256"] == expected
    assert identity["source_revision"] == f"source-sha256:{expected}"
    assert identity["contract_address"] == "0x5cfaE959BbFF6Be9e4A1F477abDCc61fAfD5eeb1"
    assert "password" not in identity


def test_finalized_claim_does_not_offer_invalid_appeal(monkeypatch):
    monkeypatch.setenv("DEEPSIGHT_RELAY_ENABLED", "1")
    monkeypatch.setattr("api.chain.load_config", lambda: {"address": "0x" + "3" * 40})
    insert_claim(status="FINALIZED")
    with SessionLocal() as db:
        db.get(ClaimRow, "clm_test").chain_claim_id = "pod-1"
        db.commit()
    with TestClient(app) as client:
        rejected = client.post("/v1/claims/clm_test/intent", json={"action": "appeal", "tx_hash": "0x" + "a" * 64})
        assert rejected.status_code == 422
        legacy = client.post("/v1/claims/clm_test/appeal", json={"tx_hash": "0x" + "a" * 64})
        assert legacy.status_code == 409


def test_wrong_wallet_cannot_use_challenge():
    app.dependency_overrides.clear()
    first, second = Account.create(), Account.create()
    with TestClient(app) as client:
        challenge = client.post("/v1/auth/challenge", json={"address": first.address}).json()
        signature = Account.sign_message(encode_defunct(text=challenge["message"]), second.key).signature.hex()
        assert client.post("/v1/auth/session", json={"challenge_id": challenge["id"], "signature": signature}).status_code == 401


@pytest.mark.parametrize("action", ["review-request", "retract", "supersede", "submit"])
def test_other_researcher_cannot_mutate_claim(action):
    insert_claim()
    app.dependency_overrides[current_user] = lambda: OTHER
    with TestClient(app) as client:
        assert client.post(f"/v1/claims/clm_test/{action}").status_code == 403


def test_retracted_claim_cannot_submit():
    insert_claim("RETRACTED")
    with TestClient(app) as client:
        assert client.post("/v1/claims/clm_test/submit").status_code == 409


@pytest.mark.parametrize("change", [
    lambda d: d["metrics"][0].update(value=-2.5),
    lambda d: d["metrics"][0].update(value="NaN"),
    lambda d: d["metrics"][0].update(value="Infinity"),
    lambda d: d["metrics"][0].update(unit="meters"),
    lambda d: d["target"].update(ra_deg=999, dec_deg=999),
    lambda d: d["cross_matches"][0].update(query_snapshot_sha256="x"),
])
def test_policy_rejects_invalid_science_or_provenance(change):
    document = _base(); change(document)
    assert evaluate(json.dumps(document), "celestial_object_evidence", "celestial-v1")[0] != "EVIDENCE_SUFFICIENT"


def contract_policy():
    # Execute only pure policy helpers, not the GenVM storage/runtime classes.
    tree = ast.parse(Path("contracts/proof_of_discovery.py").read_text())
    nodes = [node for node in tree.body if isinstance(node, ast.Assign) or (isinstance(node, ast.FunctionDef) and node.name not in ("_public_claim", "_now_iso"))]
    namespace = {"json": json}
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "contract-policy", "exec"), namespace)
    return namespace["_evaluate"]


@pytest.mark.parametrize("value", ["1e-3", "NaN", "Infinity", "-1", 2.5, True, None, "1e1000", "1e++2", "1e--2"])
def test_local_contract_policy_parity(value):
    document = _base(); document["metrics"][0]["value"] = value
    text = json.dumps(document)
    assert evaluate(text, "celestial_object_evidence", "celestial-v1") == contract_policy()(text, "celestial_object_evidence", "celestial-v1")


def test_registered_target_must_match_manifest():
    document = _base()
    text = json.dumps(document)
    assert evaluate(text, "celestial_object_evidence", "celestial-v1", "different-target") == contract_policy()(text, "celestial_object_evidence", "celestial-v1", "different-target")
    assert evaluate(text, "celestial_object_evidence", "celestial-v1", "different-target")[0] == "EVIDENCE_INSUFFICIENT"


def test_evidence_bundle_contains_exact_hashable_bytes():
    with TestClient(app) as client:
        analysis = client.post("/v1/analyses", json={"target_id": "DS-SYN-001"}).json()
        response = client.post("/v1/claims", json={"analysis_id": analysis["id"], "acknowledged": True})
        assert response.status_code == 200, response.text
        claim = response.json()
        assert client.post(f"/v1/claims/{claim['id']}/publish", json={"acknowledged": True}).status_code == 200
        bundle = client.get(f"/v1/claims/{claim['id']}/bundle").json()
        assert hashlib.sha256(bundle["manifest"].encode()).hexdigest() == bundle["manifest_sha256"]
        for digest, content in bundle["artifacts"].items():
            assert hashlib.sha256(content.encode()).hexdigest() == digest
            assert client.get(f"/v1/artifacts/{digest}").content == content.encode()
        manifest = json.loads(bundle["manifest"])
        assert manifest["diagnostics"]
        assert manifest["metrics"][0]["uncertainty"] is not None
        assert manifest["analysis"]["environment_sha256"]
        app.dependency_overrides[current_user] = lambda: OTHER
        assert client.post("/v1/claims", json={"analysis_id": analysis["id"], "acknowledged": True}).status_code == 403


def test_draft_claim_and_artifacts_are_private_until_explicit_publication():
    with TestClient(app) as client:
        analysis = client.post("/v1/analyses", json={"target_id": "DS-SYN-001"}).json()
        claim = client.post("/v1/claims", json={"analysis_id": analysis["id"], "acknowledged": True}).json()
        claim_id = claim["id"]
        digest = analysis["series_sha256"]
        app.dependency_overrides.pop(optional_user, None)
        assert all(row["id"] != claim_id for row in client.get("/v1/claims").json()["claims"])
        for suffix in ("", "/manifest", "/bundle", "/timeline", "/finality", "/operations"):
            assert client.get(f"/v1/claims/{claim_id}{suffix}").status_code == 404
        assert client.get(f"/v1/artifacts/{digest}").status_code == 401
        assert client.post(f"/v1/claims/{claim_id}/publish", json={"acknowledged": False}).status_code == 422
        token = "draft-owner-token"
        with SessionLocal() as db:
            db.add(AuthSession(token_hash=hashlib.sha256(token.encode()).hexdigest(), address=OWNER, expires=int(time.time()) + 60))
            db.commit()
        client.cookies.set("deepsight_session", token)
        assert client.get(f"/v1/claims/{claim_id}").status_code == 200
        assert client.post(f"/v1/claims/{claim_id}/publish", json={"acknowledged": True}).status_code == 200
        client.cookies.clear()
        assert client.get(f"/v1/claims/{claim_id}").status_code == 200
        assert client.get(f"/v1/artifacts/{digest}").status_code == 200


def test_only_operator_can_reconcile_unknown_broadcast(monkeypatch):
    claim_id = insert_claim()
    with SessionLocal() as db:
        db.add(ChainOperation(id="op_unknown", claim_id=claim_id, actor=OWNER,
                              action="submit", stage="register", status="unknown", payload="{}",
                              authorization="signed", signature="0x12", updated=int(time.time())))
        db.commit()
    body = {"decision": "confirmed_not_broadcast", "evidence": "Relay nonce unchanged after explorer and RPC checks"}
    with TestClient(app) as client:
        assert client.post("/v1/chain/operations/op_unknown/reconcile", json=body).status_code == 403
        monkeypatch.setenv("DEEPSIGHT_OPERATORS", OWNER)
        response = client.post("/v1/chain/operations/op_unknown/reconcile", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["status"] == "queued"
        assert client.post("/v1/chain/operations/op_unknown/reconcile", json=body).status_code == 409


def test_unpublished_analysis_and_artifact_are_owner_scoped():
    from api.db import AuthSession
    owner_token, other_token = "owner-test-token", "other-test-token"
    with SessionLocal() as db:
        db.add_all([
            AuthSession(token_hash=hashlib.sha256(owner_token.encode()).hexdigest(), address=OWNER, expires=int(time.time()) + 60),
            AuthSession(token_hash=hashlib.sha256(other_token.encode()).hexdigest(), address=OTHER, expires=int(time.time()) + 60),
        ])
        db.commit()
    with TestClient(app) as client:
        client.cookies.set("deepsight_session", owner_token)
        analysis = client.post("/v1/analyses", json={"target_id": "DS-SYN-001"}).json()
        digest = analysis["series_sha256"]
        assert client.get(f"/v1/analyses/{analysis['id']}").status_code == 200
        assert client.get(f"/v1/artifacts/{digest}").status_code == 200
        assert client.get(f"/v1/artifacts/{digest}").headers["cache-control"] == "private, no-store"
        app.dependency_overrides[current_user] = lambda: OTHER
        client.cookies.set("deepsight_session", other_token)
        assert client.get(f"/v1/analyses/{analysis['id']}").status_code == 403
        assert client.get(f"/v1/artifacts/{digest}").status_code == 404


def test_discoveries_require_finalized_chain_decision():
    insert_claim(status="FINALIZED")
    with SessionLocal() as db:
        claim = db.get(ClaimRow, "clm_test")
        claim.protocol_result = "EVIDENCE_SUFFICIENT"
        db.commit()
    with TestClient(app) as client:
        assert client.get("/v1/discoveries").json()["discoveries"] == []
    with SessionLocal() as db:
        claim = db.get(ClaimRow, "clm_test")
        claim.chain_claim_id = "pod-1"
        claim.chain_protocol_result = "EVIDENCE_SUFFICIENT"
        claim.chain_status = "FINALIZED"
        claim.chain_execution = "SUCCESS"
        claim.public = True
        db.commit()
    with TestClient(app) as client:
        assert [item["id"] for item in client.get("/v1/discoveries").json()["discoveries"]] == ["clm_test"]


def test_worker_job_persists_result_and_is_private(monkeypatch):
    monkeypatch.setattr("api.main.create_analysis", lambda body, user: {"target": body.target_id, "owner": user})
    with TestClient(app) as client:
        response = client.post("/v1/jobs", json={"kind": "analysis", "target_id": "DS-SYN-001"})
        assert response.status_code == 202
        job_id = response.json()["id"]
        assert jobs.run_one()
        result = client.get(f"/v1/jobs/{job_id}").json()
        assert result["status"] == "succeeded"
        assert result["result"]["owner"] == OWNER
        app.dependency_overrides[current_user] = lambda: OTHER
        assert client.get(f"/v1/jobs/{job_id}").status_code == 404


def queue_signed_operation(monkeypatch):
    wallet = Account.create()
    insert_claim(owner=wallet.address.lower())
    monkeypatch.setenv("DEEPSIGHT_RELAY_ENABLED", "1")
    monkeypatch.setenv("DEEPSIGHT_RELAY_ADDRESS", wallet.address.lower())
    monkeypatch.setattr("api.chain.load_config", lambda: {"address": "0x"+"3"*40})
    app.dependency_overrides[current_user] = lambda: wallet.address.lower()
    with TestClient(app) as client:
        prepared = client.post("/v1/claims/clm_test/intent", json={"action": "submit"})
        assert prepared.status_code == 200, prepared.text
        intent = prepared.json()
        signature = Account.sign_message(encode_defunct(text=intent["message"]), wallet.key).signature.hex()
        body = {"intent_id": intent["id"], "signature": signature}
        response = client.post("/v1/claims/clm_test/authorize", json=body)
        assert response.status_code == 202, response.text
        assert client.post("/v1/claims/clm_test/authorize", json=body).status_code == 401
    return response.json()["id"]


def test_outbox_waits_for_successful_finality_and_persists_chain_result(monkeypatch):
    operation_id = queue_signed_operation(monkeypatch)
    status = {"value": "ACCEPTED"}
    calls = []
    def invoke(command, config):
        calls.append(command)
        if command["action"] == "broadcast":
            return {"ok": True, "hash": "0x"+str(len(calls))*64}
        if command["action"] == "receipt":
            return {"ok": True, "status": status["value"], "execution": "SUCCESS"}
        return {"ok": True, "result": {"claim_id": "pod-1", "status": "FINALIZED", "protocol_result": "EVIDENCE_SUFFICIENT", "rationale": "Fields verified"}}
    monkeypatch.setattr("api.chain.invoke", invoke)
    assert chain_ops.execute_one()  # broadcast registration
    assert chain_ops.execute_one()  # accepted is not final
    with SessionLocal() as db:
        assert db.get(ChainOperation, operation_id).stage == "register"
        assert db.get(ClaimRow, "clm_test").chain_claim_id == ""
    status["value"] = "FINALIZED"
    chain_ops.execute_one()  # register finalized, queue review
    chain_ops.execute_one()  # broadcast review
    chain_ops.execute_one()  # review finalized
    with SessionLocal() as db:
        assert db.get(ChainOperation, operation_id).status == "done"
        claim = db.get(ClaimRow, "clm_test")
        assert claim.chain_protocol_result == "EVIDENCE_SUFFICIENT"
        assert claim.protocol_result == ""
        assert claim.chain_execution == "SUCCESS"
    assert len([c for c in calls if c["action"] == "broadcast"]) == 2


def test_wallet_transactions_are_verified_and_reviewed_without_relay(monkeypatch):
    insert_claim()
    contract = "0x" + "3" * 40
    monkeypatch.setenv("DEEPSIGHT_RELAY_ENABLED", "0")
    monkeypatch.setenv("DEEPSIGHT_V4_CONTRACT_ADDRESS", contract)
    monkeypatch.setattr("api.chain.load_config", lambda: {"address": contract})
    calls = []
    def invoke(command, config):
        calls.append(command)
        if command["action"] == "inspect":
            with SessionLocal() as db:
                claim = db.get(ClaimRow, "clm_test")
                stage = "review" if claim.chain_claim_id else "register"
                payload = {"contract": contract, "manifest_hash": claim.manifest_hash}
                expected = chain_ops._command(type("Op", (), {"stage": stage})(), claim, payload)
            return {"ok": True, "from": OWNER, "to": contract,
                    "decoded": {"callData": {"method": expected["method"], "args": expected["args"]}}}
        if command["action"] == "receipt":
            return {"ok": True, "status": "FINALIZED", "execution": "SUCCESS"}
        if command["method"] == "read_claim_by_manifest":
            return {"ok": True, "result": {"claim_id": "pod-wallet"}}
        return {"ok": True, "result": {"status": "NEEDS_REVIEW", "protocol_result": "NEEDS_HUMAN_REVIEW", "rationale": "Archive unavailable"}}
    monkeypatch.setattr("api.chain.invoke", invoke)
    with TestClient(app) as client:
        assert client.post("/v1/claims/clm_test/wallet/prepare", json={"action": "submit"}).status_code == 422
        with SessionLocal() as db:
            assert db.get(ClaimRow, "clm_test").public is False
        prepared = client.post("/v1/claims/clm_test/wallet/prepare", json={"action": "submit", "publish_acknowledged": True})
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()["method"] == "register_claim"
        bad = client.post("/v1/claims/clm_test/wallet/transaction", json={"action": "submit", "tx_hash": "0x" + "a" * 64})
        assert bad.status_code == 202, bad.text
        assert client.post("/v1/claims/clm_test/wallet/transaction", json={"action": "submit", "tx_hash": "0x" + "a" * 64}).status_code == 202
        assert chain_ops.execute_one()
        assert not any(call["action"] == "broadcast" for call in calls)
        with SessionLocal() as db:
            claim = db.get(ClaimRow, "clm_test")
            assert claim.chain_claim_id == "pod-wallet"
            assert db.get(ChainOperation, bad.json()["id"]).status == "done"
        review = client.post("/v1/claims/clm_test/wallet/prepare", json={"action": "review"})
        assert review.status_code == 200
        assert review.json()["method"] == "request_evidence_review"
        attached = client.post("/v1/claims/clm_test/wallet/transaction", json={"action": "review", "tx_hash": "0x" + "b" * 64})
        assert attached.status_code == 202, attached.text
        assert chain_ops.execute_one()
        with SessionLocal() as db:
            claim = db.get(ClaimRow, "clm_test")
            assert claim.chain_protocol_result == "NEEDS_HUMAN_REVIEW"
            assert claim.status == "NEEDS_REVIEW"
            assert db.get(ChainOperation, attached.json()["id"]).status == "done"


def test_wallet_transaction_rejects_other_sender_and_call(monkeypatch):
    insert_claim()
    contract = "0x" + "3" * 40
    monkeypatch.setattr("api.chain.load_config", lambda: {"address": contract})
    with SessionLocal() as db:
        db.get(ClaimRow, "clm_test").public = True
        db.commit()
    with TestClient(app) as client:
        monkeypatch.setattr("api.chain.invoke", lambda *args: {"ok": True, "from": OTHER, "to": contract,
            "decoded": {"callData": {"method": "register_claim", "args": []}}})
        assert client.post("/v1/claims/clm_test/wallet/transaction", json={"action": "submit", "tx_hash": "0x" + "a" * 64}).status_code == 403
        monkeypatch.setattr("api.chain.invoke", lambda *args: {"ok": True, "from": OWNER, "to": contract,
            "decoded": {"callData": {"method": "retract_claim", "args": ["pod-other"]}}})
        assert client.post("/v1/claims/clm_test/wallet/transaction", json={"action": "submit", "tx_hash": "0x" + "a" * 64}).status_code == 403


def test_other_researcher_can_prepare_wallet_challenge(monkeypatch):
    insert_claim(status="NEEDS_REVIEW")
    monkeypatch.setattr("api.chain.load_config", lambda: {"address": "0x" + "3" * 40})
    with SessionLocal() as db:
        claim = db.get(ClaimRow, "clm_test")
        claim.chain_claim_id = "pod-wallet"
        claim.public = True
        db.commit()
    app.dependency_overrides[current_user] = lambda: OTHER
    with TestClient(app) as client:
        prepared = client.post("/v1/claims/clm_test/wallet/prepare", json={
            "action": "challenge", "reason": "Independent reanalysis disputes the result",
        })
        assert prepared.status_code == 200, prepared.text
        assert prepared.json()["method"] == "challenge_claim"
        assert client.post("/v1/claims/clm_test/wallet/prepare", json={"action": "retract"}).status_code == 403


def test_supersede_publishes_replacement_before_broadcast(monkeypatch):
    wallet = Account.create()
    monkeypatch.setenv("DEEPSIGHT_RELAY_ENABLED", "1")
    monkeypatch.setenv("DEEPSIGHT_RELAY_ADDRESS", wallet.address.lower())
    monkeypatch.setattr("api.chain.load_config", lambda: {"address": "0x" + "3" * 40})
    insert_claim(status="FINALIZED", owner=wallet.address.lower())
    with SessionLocal() as db:
        db.get(ClaimRow, "clm_test").chain_claim_id = "pod-1"
        db.commit()
    app.dependency_overrides[current_user] = lambda: wallet.address.lower()
    with TestClient(app) as client:
        response = client.post("/v1/claims/clm_test/intent", json={"action": "supersede"})
        assert response.status_code == 200, response.text
        intent = response.json()
        signature = Account.sign_message(encode_defunct(text=intent["message"]), wallet.key).signature.hex()
        response = client.post("/v1/claims/clm_test/authorize", json={"intent_id": intent["id"], "signature": signature})
        assert response.status_code == 202, response.text
        with SessionLocal() as db:
            operation = db.get(ChainOperation, response.json()["id"])
            old = db.get(ClaimRow, "clm_test")
            command = chain_ops._command(operation, old, json.loads(operation.payload))
            replacement_id = json.loads(operation.payload)["replacement_id"]
            replacement = db.get(ClaimRow, replacement_id)
            assert replacement.status == "PENDING_CHAIN"
            assert command["args"][2].endswith(f"/v1/claims/{replacement_id}/manifest")
            assert client.get(f"/v1/claims/{replacement_id}/manifest").status_code == 200
            operation.status = "failed"
            db.commit()
        retry = client.post("/v1/claims/clm_test/intent", json={"action": "supersede"})
        assert retry.status_code == 200, retry.text
        with SessionLocal() as db:
            assert json.loads(db.get(ChainIntent, retry.json()["id"]).payload)["replacement_id"] == replacement_id


def test_outbox_retries_stale_contract_view_after_finality(monkeypatch):
    operation_id = queue_signed_operation(monkeypatch)
    view_status = {"value": "SUBMITTED"}

    def invoke(command, config):
        if command["action"] == "broadcast":
            return {"ok": True, "hash": "0x" + "a" * 64}
        if command["action"] == "receipt":
            return {"ok": True, "status": "FINALIZED", "execution": "SUCCESS"}
        if command["method"] == "read_claim_by_manifest":
            return {"ok": True, "result": {"claim_id": "pod-1"}}
        return {"ok": True, "result": {"status": view_status["value"], "protocol_result": "EVIDENCE_SUFFICIENT"}}

    monkeypatch.setattr("api.chain.invoke", invoke)
    for _ in range(4):
        assert chain_ops.execute_one()
    assert chain_ops.execute_one() is False  # stale reads back off instead of hammering RPC
    with SessionLocal() as db:
        operation = db.get(ChainOperation, operation_id)
        assert operation.status == "submitted"
        operation.updated = 0
        db.commit()
    view_status["value"] = "FINALIZED"
    assert chain_ops.execute_one()
    with SessionLocal() as db:
        assert db.get(ChainOperation, operation_id).status == "done"


def test_uncertain_broadcast_is_not_automatically_repeated(monkeypatch):
    operation_id = queue_signed_operation(monkeypatch)
    calls = []
    def unavailable(*args):
        calls.append(args)
        raise TimeoutError()
    monkeypatch.setattr("api.chain.invoke", unavailable)
    chain_ops.execute_one()
    chain_ops.execute_one()
    with SessionLocal() as db:
        assert db.get(ChainOperation, operation_id).status == "unknown"
    assert len(calls) == 1


def test_misconfigured_operation_yields_outbox_to_other_claims(monkeypatch):
    operation_id = queue_signed_operation(monkeypatch)
    monkeypatch.setenv("DEEPSIGHT_V4_CONTRACT_ADDRESS", "0x" + "5" * 40)
    with SessionLocal() as db:
        old = db.get(ChainOperation, operation_id)
        db.add(ChainOperation(id="op_other", claim_id=old.claim_id, actor=old.actor,
                              action="submit", stage="register", status="queued",
                              payload=json.dumps({"contract": "0x" + "4" * 40}),
                              authorization="test", signature="test", updated=old.updated + 1))
        db.commit()
    assert chain_ops.execute_one()
    with SessionLocal() as db:
        assert db.get(ChainOperation, operation_id).updated > int(time.time())
        db.get(ChainOperation, "op_other").updated = int(time.time()) - 1
        db.commit()
    assert chain_ops.execute_one()
    with SessionLocal() as db:
        assert db.get(ChainOperation, "op_other").updated > int(time.time())


def test_finalized_failed_execution_is_not_success(monkeypatch):
    operation_id = queue_signed_operation(monkeypatch)
    def invoke(command, config):
        if command["action"] == "broadcast":
            return {"ok": True, "hash": "0x" + "a" * 64}
        return {"ok": True, "status": "FINALIZED", "execution": "FAILED"}
    monkeypatch.setattr("api.chain.invoke", invoke)
    chain_ops.execute_one()
    chain_ops.execute_one()
    with SessionLocal() as db:
        assert db.get(ChainOperation, operation_id).status == "failed"
    with TestClient(app) as client:
        assert client.get("/v1/claims/clm_test/finality").json()["finalized_on_chain"] is False


def test_pending_operation_blocks_local_retraction(monkeypatch):
    queue_signed_operation(monkeypatch)
    with TestClient(app) as client:
        assert client.post("/v1/claims/clm_test/retract").status_code == 409


def test_corrupt_artifact_is_not_served():
    from api.db import ArtifactRow
    digest = evidence.put_json({"flux": [1, 2]})
    with SessionLocal() as db:
        db.get(ArtifactRow, digest).content = "corrupt"
        db.commit()
    with TestClient(app) as client:
        assert client.get(f"/v1/artifacts/{digest}").status_code == 409


def test_object_store_artifact_round_trip_and_checksum(monkeypatch):
    import io
    from api.db import ArtifactRow
    objects = {}
    class Store:
        def put_object(self, *, Bucket, Key, Body, ContentType):
            objects[(Bucket, Key)] = Body
        def get_object(self, *, Bucket, Key):
            return {"Body": io.BytesIO(objects[(Bucket, Key)])}
    monkeypatch.setenv("DEEPSIGHT_S3_BUCKET", "evidence-test")
    monkeypatch.setattr("boto3.client", lambda *args, **kwargs: Store())
    digest = evidence.put_json({"samples": [1, 2, 3]})
    with SessionLocal() as db:
        assert db.get(ArtifactRow, digest).content == f"s3:{digest}"
    assert json.loads(evidence.read(digest)) == {"samples": [1, 2, 3]}
    objects[("evidence-test", f"artifacts/{digest}.json")] = b"corrupted"
    with pytest.raises(Exception) as exc:
        evidence.read(digest)
    assert exc.value.status_code == 409


def test_research_run_history_is_scoped_to_owner(monkeypatch):
    monkeypatch.setattr("api.main.create_analysis", lambda body, user: {"id": "an_saved", "target": body.target_id})
    with TestClient(app) as client:
        client.post("/v1/jobs", json={"kind": "analysis", "target_id": "DS-SYN-001"})
        jobs.run_one()
        rows = client.get("/v1/jobs").json()["jobs"]
        assert rows[0]["href"] == "/lab?analysis=an_saved"
        app.dependency_overrides[current_user] = lambda: OTHER
        assert client.get("/v1/jobs").json()["jobs"] == []
