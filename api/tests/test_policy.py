import json

from api.manifest import canonicalize, sha256_text
from api.policy import RESULT_INSUFFICIENT, RESULT_REVIEW, RESULT_SUFFICIENT, evaluate


def _base() -> dict:
    return {
        "schema_version": "1.1",
        "claimant_address": "0x" + "1" * 40,
        "researcher_address": "0x" + "2" * 40,
        "claim_type": "celestial_object_evidence",
        "policy_version": "celestial-v1",
        "target": {"id": "TIC-1", "ra_deg": 10.0, "dec_deg": -20.0},
        "archive": {"name": "MAST", "observation_ids": ["obs-1"]},
        "analysis": {"git_commit": "abc", "container_digest": "sha256:" + "d" * 64},
        "metrics": [
            {"name": "period", "value": 2.5, "unit": "d", "uncertainty": 0.01, "uncertainty_method": "residual_bootstrap_white_noise_v1"},
            {"name": "depth", "value": 0.01, "unit": "relative_flux"},
        ],
        "artifacts": [{"sha256": "a" * 64, "uri": "s3://evidence/curve"}],
        "cross_matches": [
            {
                "catalogue": "NASA Exoplanet Archive",
                "result": "no_exact_match",
                "query_snapshot_sha256": "b" * 64,
            }
        ],
        "false_positive_tests": ["odd_even", "secondary_eclipse"],
        "limitations": ["Not scientifically confirmed"],
        "scientific_status": "unconfirmed_candidate",
    }


def test_complete_mast_manifest_is_sufficient_but_not_a_discovery():
    result, rationale = evaluate(json.dumps(_base()), "celestial_object_evidence", "celestial-v1")
    assert result == RESULT_SUFFICIENT
    assert "not a scientific confirmation" in rationale


def test_confirmation_language_is_rejected():
    document = _base()
    document["scientific_status"] = "planet_confirmed"
    result, rationale = evaluate(json.dumps(document), "celestial_object_evidence", "celestial-v1")
    assert result == RESULT_INSUFFICIENT
    assert "cannot certify" in rationale


def test_synthetic_archive_needs_a_person():
    document = _base()
    document["archive"]["name"] = "DeepSight synthetic calibration"
    result, rationale = evaluate(json.dumps(document), "celestial_object_evidence", "celestial-v1")
    assert result == RESULT_REVIEW
    assert "allowlist" in rationale


def test_missing_artifact_is_insufficient():
    document = _base()
    document["artifacts"] = []
    result, _rationale = evaluate(json.dumps(document), "celestial_object_evidence", "celestial-v1")
    assert result == RESULT_INSUFFICIENT


def test_radio_without_off_target_needs_review():
    document = {
        "schema_version": "1.1",
        "claimant_address": "0x" + "1" * 40,
        "researcher_address": "0x" + "2" * 40,
        "claim_type": "radio_signal_integrity",
        "policy_version": "signal-v1",
        "scientific_status": "inconclusive",
        "archive": {"name": "Breakthrough Listen"},
        "signal": {
            "observation_id": "bl-1",
            "frequency_range": "1100-1200 MHz",
            "time_range": "2024-01-01/2024-01-01",
            "snr_method": "band-integrated",
            "calibration": "noise diode",
        },
        "artifacts": [{"sha256": "c" * 64}],
        "rfi_tests": ["off_axis_repeat"],
        "off_target_comparison": "unavailable",
        "analysis": {"git_commit": "abc", "container_digest": "sha256:" + "d" * 64},
        "limitations": ["An anomaly is not a technosignature"],
    }
    result, rationale = evaluate(json.dumps(document), "radio_signal_integrity", "signal-v1")
    assert result == RESULT_REVIEW
    assert "off-target" in rationale


def test_canonical_hash_is_stable():
    text = canonicalize({"b": 1, "a": [2, 3]})
    assert text == '{"a":[2,3],"b":1}'
    assert sha256_text(text) == sha256_text(text)
