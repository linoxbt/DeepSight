from fastapi.testclient import TestClient

from api.chain import review_argument
from api.main import app

client = TestClient(app)
client.__enter__()


def test_review_argument_keeps_manifest_json_a_cli_string():
    argument = review_argument('{"schema_version":"1.1"}')
    assert argument == 'ds1:{"schema_version":"1.1"}'
    assert not argument.startswith("{")


def test_challenge_and_retract_stay_local_without_a_contract():
    created = client.post("/v1/analyses", json={"target_id": "DS-SYN-001"})
    claim = client.post("/v1/claims", json={"analysis_id": created.json()["id"], "acknowledged": True})
    claim_id = claim.json()["id"]
    reviewed = client.post(f"/v1/claims/{claim_id}/review-request")
    assert reviewed.json()["status"] == "NEEDS_REVIEW"

    noted = client.post(f"/v1/claims/{claim_id}/review-note", json={"note": "Provenance still needs a person."})
    assert noted.status_code == 200

    challenged = client.post(
        f"/v1/claims/{claim_id}/challenge",
        json={"reason": "The calibration series is not an archive observation."},
    )
    assert challenged.status_code == 200
    assert challenged.json()["status"] == "CHALLENGED"
    assert challenged.json()["chain_status"] == "not_submitted"
    assert len(challenged.json()["challenge_reason_hash"]) == 64

    blocked = client.post("/v1/claims/{}/submit".format(claim_id))
    assert blocked.status_code == 409  # A challenged claim is ineligible even without a relay.

    retracted = client.post(f"/v1/claims/{claim_id}/retract")
    assert retracted.status_code == 200
    assert retracted.json()["status"] == "RETRACTED"


def test_radio_claim_route_uses_a_screen_without_network(monkeypatch):
    from uuid import uuid4

    token = uuid4().hex[:8]

    def fake_analyze(_cache):
        return {
            "target_name": f"Voyager1-{token}",
            "synthetic": False,
            "archive": "Breakthrough Listen",
            "observation_id": "Voyager1.single_coarse.fine_res",
            "scientific_status": "known_object",
            "frequency_range": "8418-8438 MHz",
            "time_range": "MJD 57000",
            "snr_method": "median-absolute-deviation of the time-averaged spectrum",
            "calibration": "Archive HDF5 as released. DeepSight did not recalibrate the bandpass.",
            "off_target_comparison": "unavailable",
            "rfi_tests": ["narrowband_mad", "band_edge", "time_persistence"],
            "metrics": {
                "snr_proxy": 12.5,
                "n_hits": 1,
                "n_spans": 1,
                "edge_hit_fraction": 0,
                "peak_time_fraction": 1,
            },
            "hits": [{"frequency_mhz": 8420.1, "mad_score": 12.5, "channel_start": 1, "channel_stop": 1}],
            "plot": {"frequency_mhz": [8420.1], "relative_power": [1.0]},
            "limitations": [
                "A narrowband excess is not a technosignature and is not an extraterrestrial detection.",
                "No off-target pointing was compared, so this package cannot satisfy the signal policy on its own.",
            ],
            "artifact_sha256": "cd" * 32,
            "data_uri": "http://example.test/voyager.h5",
            "product_filename": "Voyager1.single_coarse.fine_res.h5",
            "note": "The screen flags narrow channels. It does not verify an alien signal.",
        }

    monkeypatch.setattr("api.main.analyze_tutorial", fake_analyze)
    analyzed = client.post("/v1/radio/analyze")
    assert analyzed.status_code == 200
    claim = client.post("/v1/radio/claims", json={"analysis_id": analyzed.json()["id"], "acknowledged": True})
    assert claim.status_code == 200
    reviewed = client.post(f"/v1/claims/{claim.json()['id']}/review-request")
    assert reviewed.json()["protocol_result"] == "NEEDS_HUMAN_REVIEW"
    assert reviewed.json()["scientific_confirmation"] is False
