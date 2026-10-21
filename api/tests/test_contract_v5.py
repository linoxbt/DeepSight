"""Exercise the v5 state transitions without pretending to reproduce FITS data."""

import ast
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SOURCE = Path("contracts/proof_of_discovery_v5.py").read_text()


def contract_method(name, namespace):
    tree = ast.parse(SOURCE)
    contract = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ProofOfDiscovery")
    method = next(node for node in contract.body if isinstance(node, ast.FunctionDef) and node.name == name)
    method.decorator_list = []
    exec(compile(ast.Module(body=[method], type_ignores=[]), "v5-contract", "exec"), namespace)
    return namespace[name]


def test_catalogue_match_has_narrow_result_even_for_unverified_observation():
    document = {"target": {"id": "TIC-1"}, "archive": {"observation_ids": ["unrelated"]}}
    published = json.dumps(document)
    digest = hashlib.sha256(published.encode()).hexdigest()
    claim = SimpleNamespace(claim_id="pod-1", manifest_hash=digest, source_ref="https://example.org/manifest",
                            claim_type="celestial_object_evidence", policy_version="celestial-v5", target_id="TIC-1",
                            protocol_result="", rationale="", status="SUBMITTED", evidence_summary_hash="", updated_at="")
    registry = SimpleNamespace(claims={"pod-1": claim}, _editable=lambda _id, _states: claim,
                               _fetch_manifest=lambda _source: published)
    namespace = {"hashlib": hashlib, "json": json, "MAX_SUMMARY_CHARS": 8000,
                 "STATUS_SUBMITTED": "SUBMITTED", "STATUS_REVIEW": "NEEDS_REVIEW",
                 "STATUS_FINALIZED": "FINALIZED", "TYPE_CELESTIAL": "celestial_object_evidence",
                 "RESULT_REVIEW": "NEEDS_HUMAN_REVIEW", "RESULT_CATALOGUE": "CATALOGUE_CONSISTENT",
                 "_evaluate": lambda *_args: ("NEEDS_HUMAN_REVIEW", "Independent archive comparison required for measured period and depth."),
                 "_verify_archive_measurements": lambda _document: "matched", "_now_iso": lambda: "now"}
    review = contract_method("request_evidence_review", namespace)
    assert review(registry, "pod-1", published) == "CATALOGUE_CONSISTENT"
    assert claim.status == "FINALIZED"
    assert "not independently verified" in claim.rationale


def test_archive_outage_cannot_become_positive_result():
    document = {"target": {"id": "TIC-1"}}
    published = json.dumps(document)
    claim = SimpleNamespace(claim_id="pod-1", manifest_hash=hashlib.sha256(published.encode()).hexdigest(),
                            source_ref="https://example.org/manifest", claim_type="celestial_object_evidence",
                            policy_version="celestial-v5", target_id="TIC-1", protocol_result="", rationale="",
                            status="SUBMITTED", evidence_summary_hash="", updated_at="")
    registry = SimpleNamespace(claims={"pod-1": claim}, _editable=lambda _id, _states: claim,
                               _fetch_manifest=lambda _source: published)
    namespace = {"hashlib": hashlib, "json": json, "MAX_SUMMARY_CHARS": 8000,
                 "STATUS_SUBMITTED": "SUBMITTED", "STATUS_REVIEW": "NEEDS_REVIEW",
                 "STATUS_FINALIZED": "FINALIZED", "TYPE_CELESTIAL": "celestial_object_evidence",
                 "RESULT_REVIEW": "NEEDS_HUMAN_REVIEW", "RESULT_CATALOGUE": "CATALOGUE_CONSISTENT",
                 "_evaluate": lambda *_args: ("NEEDS_HUMAN_REVIEW", "Independent archive comparison required for measured period and depth."),
                 "_verify_archive_measurements": lambda _document: "NASA archive comparison was unavailable",
                 "_join": lambda parts: " ".join(parts), "_now_iso": lambda: "now"}
    review = contract_method("request_evidence_review", namespace)
    assert review(registry, "pod-1", published) == "NEEDS_HUMAN_REVIEW"
    assert claim.status == "NEEDS_REVIEW"


def test_unverified_objection_preserves_assessment_and_rejects_replacement():
    class UserError(Exception):
        pass

    claim = SimpleNamespace(claim_id="pod-1", status="FINALIZED", protocol_result="CATALOGUE_CONSISTENT",
                            challenge_reason_hash="", challenge_actor="", challenge_created_at="", updated_at="")
    registry = SimpleNamespace(claims={"pod-1": claim}, _get=lambda _id: claim)
    namespace = {"_require_sha256": lambda value, _field: value, "_now_iso": lambda: "now",
                 "STATUS_FINALIZED": "FINALIZED", "STATUS_REVIEW": "NEEDS_REVIEW",
                 "ERROR_EXPECTED": "[EXPECTED]", "gl": SimpleNamespace(vm=SimpleNamespace(UserError=UserError),
                     message=SimpleNamespace(sender_address="0x" + "2" * 40))}
    challenge = contract_method("challenge_claim", namespace)
    challenge(registry, "pod-1", "a" * 64)
    assert claim.status == "FINALIZED"
    assert claim.protocol_result == "CATALOGUE_CONSISTENT"
    assert claim.challenge_reason_hash == "a" * 64
    assert claim.challenge_actor == "0x" + "2" * 40
    with pytest.raises(UserError, match="already has an objection"):
        challenge(registry, "pod-1", "b" * 64)
    assert claim.challenge_reason_hash == "a" * 64
