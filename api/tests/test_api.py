from fastapi.testclient import TestClient
import time

from api.db import ServiceHeartbeat, SessionLocal

from api.main import app


client = TestClient(app)
client.__enter__()


def test_health_reports_archive_clients_and_unconfigured_chain():
    response = client.get("/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["live_archive"] is True
    assert body["exoplanet_tap"] is True
    assert body["gaia"] is True
    assert body["jpl_horizons"] is True
    assert body["breakthrough_listen"] is True
    assert body["genlayer_configured"] is False


def test_readiness_reports_worker_failure_and_recovery():
    assert client.get("/v1/ready").status_code == 503
    with SessionLocal() as db:
        db.add(ServiceHeartbeat(name="worker", updated=int(time.time()), detail="running"))
        db.commit()
    ready = client.get("/v1/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["database"] is True
    assert ready.json()["checks"]["worker"] is True


def test_analysis_claim_and_review_keep_science_unconfirmed():
    created = client.post("/v1/analyses", json={"target_id": "DS-SYN-001"})
    assert created.status_code == 200
    analysis = created.json()
    assert abs(analysis["metrics"]["period_days"] - 2.507) / 2.507 < 0.01
    assert analysis["cross_match"]["result"] == "no_exact_match"
    assert analysis["target"]["synthetic"] is True

    preflight = client.post("/v1/evidence/preflight", json={"analysis_id": analysis["id"]})
    assert preflight.status_code == 200
    assert preflight.json()["ready"] is True
    archive_item = next(item for item in preflight.json()["items"] if item["id"] == "archive")
    assert archive_item["status"] == "warn"

    blocked = client.post("/v1/claims", json={"analysis_id": analysis["id"], "acknowledged": False})
    assert blocked.status_code == 422

    claim = client.post("/v1/claims", json={"analysis_id": analysis["id"], "acknowledged": True})
    assert claim.status_code == 200
    claim_id = claim.json()["id"]
    assert claim.json()["scientific_status"] == "unconfirmed_candidate"
    assert claim.json()["chain_status"] == "not_submitted"
    public_record = next(row for row in client.get("/v1/claims").json()["claims"] if row["id"] == claim_id)
    assert public_record["target_name"] == analysis["target"]["id"]
    assert public_record["summary_metrics"]["period_days"]["value"] == claim.json()["summary_metrics"]["period_days"]["value"]

    reviewed = client.post(f"/v1/claims/{claim_id}/review-request")
    assert reviewed.status_code == 200
    assert reviewed.json()["protocol_result"] == "NEEDS_HUMAN_REVIEW"
    assert reviewed.json()["scientific_confirmation"] is False

    finality = client.get(f"/v1/claims/{claim_id}/finality")
    assert finality.json()["finalized_on_chain"] is False

    discoveries = client.get("/v1/discoveries")
    assert discoveries.json()["discoveries"] == []


def test_period_coincidence_control_is_labeled():
    created = client.post("/v1/analyses", json={"target_id": "DS-SYN-002"})
    assert created.status_code == 200
    body = created.json()
    assert body["cross_match"]["result"] == "period_coincidence"
    assert any(flag["code"] == "period_coincidence" for flag in body["quality_flags"])
