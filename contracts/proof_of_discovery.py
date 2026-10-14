# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Proof of Discovery registry.

Validators record an evidence manifest and apply a bounded policy to it.
The outcome is evidence sufficiency. It is never a scientific confirmation
of a planet, transient, or extraterrestrial signal.
"""

from genlayer import *
from dataclasses import dataclass
import hashlib
import json


ERROR_EXPECTED = "[EXPECTED]"

RESULT_SUFFICIENT = "EVIDENCE_SUFFICIENT"
RESULT_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
RESULT_REVIEW = "NEEDS_HUMAN_REVIEW"

STATUS_SUBMITTED = "SUBMITTED"
STATUS_FINALIZED = "FINALIZED"
STATUS_REVIEW = "NEEDS_REVIEW"
STATUS_CHALLENGED = "CHALLENGED"
STATUS_SUPERSEDED = "SUPERSEDED"
STATUS_RETRACTED = "RETRACTED"

POLICY_CELESTIAL = "celestial-v1"
POLICY_SIGNAL = "signal-v1"
TYPE_CELESTIAL = "celestial_object_evidence"
TYPE_SIGNAL = "radio_signal_integrity"

CELESTIAL_ARCHIVES = ("MAST", "NASA Exoplanet Archive", "Gaia", "JPL Horizons")
SIGNAL_ARCHIVES = ("Breakthrough Listen",)
ALLOWED_SCIENCE = (
    "unconfirmed_candidate",
    "known_object",
    "artifact",
    "inconclusive",
)
CONFIRMATION_CLAIMS = (
    "confirmed",
    "planet_confirmed",
    "confirmed_planet",
    "alien_confirmed",
    "extraterrestrial",
    "technosignature",
    "verified_discovery",
    "discovery_confirmed",
)

MAX_SUMMARY_CHARS = 8000
MAX_RATIONALE_CHARS = 600
MAX_ID_CHARS = 80
MAX_REF_CHARS = 200


@allow_storage
@dataclass
class Claim:
    claim_id: str
    claimant: Address
    manifest_hash: str
    claim_type: str
    policy_version: str
    source_ref: str
    target_id: str
    status: str
    protocol_result: str
    rationale: str
    evidence_summary_hash: str
    supersedes: str
    superseded_by: str
    challenge_reason_hash: str
    created_at: str
    updated_at: str


class ProofOfDiscovery(gl.Contract):
    claims: TreeMap[str, Claim]
    manifest_index: TreeMap[str, str]
    claim_order: DynArray[str]
    next_id: u256

    def __init__(self):
        self.next_id = u256(1)

    @gl.public.write
    def register_claim(
        self,
        manifest_hash: str,
        claim_type: str,
        policy_version: str,
        source_ref: str,
        target_id: str,
    ) -> str:
        manifest_hash = _require_sha256(manifest_hash, "manifest_hash")
        claim_type, policy_version = _require_policy_pair(claim_type, policy_version)
        source_ref = _require_text(source_ref, "source_ref", MAX_REF_CHARS)
        target_id = _require_text(target_id, "target_id", MAX_ID_CHARS)
        if manifest_hash in self.manifest_index:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Manifest hash is already registered"
            )

        claim_id = f"pod-{int(self.next_id)}"
        self.next_id = self.next_id + u256(1)
        now = _now_iso()
        self.claims[claim_id] = Claim(
            claim_id=claim_id,
            claimant=gl.message.sender_address,
            manifest_hash=manifest_hash,
            claim_type=claim_type,
            policy_version=policy_version,
            source_ref=source_ref,
            target_id=target_id,
            status=STATUS_SUBMITTED,
            protocol_result="",
            rationale="",
            evidence_summary_hash="",
            supersedes="",
            superseded_by="",
            challenge_reason_hash="",
            created_at=now,
            updated_at=now,
        )
        self.manifest_index[manifest_hash] = claim_id
        self.claim_order.append(claim_id)
        return claim_id

    @gl.public.write
    def request_evidence_review(self, claim_id: str, evidence_summary: str) -> str:
        claim = self._editable(claim_id, (STATUS_SUBMITTED,))
        # The CLI JSON parser treats a leading "{" as a dict. Callers send the
        # canonical manifest as a string with this prefix; the hash covers the
        # manifest only.
        if evidence_summary.startswith("ds1:"):
            evidence_summary = evidence_summary[4:]
        if len(evidence_summary) == 0 or len(evidence_summary) > MAX_SUMMARY_CHARS:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Evidence summary must be 1 to {MAX_SUMMARY_CHARS} characters"
            )
        digest = hashlib.sha256(evidence_summary.encode("utf-8")).hexdigest()
        if digest != claim.manifest_hash:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Evidence summary hash does not match the registered manifest"
            )
        result, rationale = _evaluate(
            evidence_summary, claim.claim_type, claim.policy_version
        )
        claim.evidence_summary_hash = digest
        claim.protocol_result = result
        claim.rationale = rationale
        claim.updated_at = _now_iso()
        if result == RESULT_REVIEW:
            claim.status = STATUS_REVIEW
        else:
            claim.status = STATUS_FINALIZED
        self.claims[claim.claim_id] = claim
        return result

    @gl.public.write
    def challenge_claim(self, claim_id: str, reason_hash: str) -> None:
        reason_hash = _require_sha256(reason_hash, "reason_hash")
        claim = self._get(claim_id)
        if claim.status not in (STATUS_FINALIZED, STATUS_REVIEW):
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Cannot challenge in status '{claim.status}'"
            )
        claim.status = STATUS_CHALLENGED
        claim.challenge_reason_hash = reason_hash
        claim.updated_at = _now_iso()
        self.claims[claim.claim_id] = claim

    @gl.public.write
    def supersede_claim(
        self, claim_id: str, new_manifest_hash: str, source_ref: str
    ) -> str:
        new_manifest_hash = _require_sha256(new_manifest_hash, "new_manifest_hash")
        source_ref = _require_text(source_ref, "source_ref", MAX_REF_CHARS)
        claim = self._editable(claim_id, (STATUS_FINALIZED, STATUS_REVIEW, STATUS_CHALLENGED))
        if new_manifest_hash in self.manifest_index:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Replacement manifest hash is already registered"
            )
        if new_manifest_hash == claim.manifest_hash:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Replacement manifest must differ from the current one"
            )

        new_id = f"pod-{int(self.next_id)}"
        self.next_id = self.next_id + u256(1)
        now = _now_iso()
        self.claims[new_id] = Claim(
            claim_id=new_id,
            claimant=claim.claimant,
            manifest_hash=new_manifest_hash,
            claim_type=claim.claim_type,
            policy_version=claim.policy_version,
            source_ref=source_ref,
            target_id=claim.target_id,
            status=STATUS_SUBMITTED,
            protocol_result="",
            rationale="",
            evidence_summary_hash="",
            supersedes=claim.claim_id,
            superseded_by="",
            challenge_reason_hash="",
            created_at=now,
            updated_at=now,
        )
        self.manifest_index[new_manifest_hash] = new_id
        self.claim_order.append(new_id)
        claim.status = STATUS_SUPERSEDED
        claim.superseded_by = new_id
        claim.updated_at = now
        self.claims[claim.claim_id] = claim
        return new_id

    @gl.public.write
    def retract_claim(self, claim_id: str) -> None:
        claim = self._editable(
            claim_id,
            (STATUS_SUBMITTED, STATUS_REVIEW, STATUS_FINALIZED, STATUS_CHALLENGED),
        )
        claim.status = STATUS_RETRACTED
        claim.updated_at = _now_iso()
        self.claims[claim.claim_id] = claim

    @gl.public.view
    def read_claim(self, claim_id: str) -> dict:
        claim = self._get(claim_id)
        return _public_claim(claim)

    @gl.public.view
    def read_claim_by_manifest(self, manifest_hash: str) -> dict:
        manifest_hash = manifest_hash.strip().lower()
        if manifest_hash not in self.manifest_index:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Manifest hash is not registered")
        return _public_claim(self.claims[self.manifest_index[manifest_hash]])

    @gl.public.view
    def list_claim_ids(self) -> list[str]:
        return [claim_id for claim_id in self.claim_order]

    def _get(self, claim_id: str) -> Claim:
        if claim_id not in self.claims:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Claim '{claim_id}' does not exist")
        return self.claims[claim_id]

    def _editable(self, claim_id: str, allowed: tuple[str, ...]) -> Claim:
        claim = self._get(claim_id)
        if gl.message.sender_address != claim.claimant:
            raise gl.vm.UserError(f"{ERROR_EXPECTED} Only the claimant can update this claim")
        if claim.status not in allowed:
            raise gl.vm.UserError(
                f"{ERROR_EXPECTED} Cannot update a claim in status '{claim.status}'"
            )
        return claim


def _now_iso() -> str:
    return str(gl.message_raw["datetime"])


def _public_claim(claim: Claim) -> dict:
    return {
        "claim_id": claim.claim_id,
        "claimant": str(claim.claimant),
        "manifest_hash": claim.manifest_hash,
        "claim_type": claim.claim_type,
        "policy_version": claim.policy_version,
        "source_ref": claim.source_ref,
        "target_id": claim.target_id,
        "status": claim.status,
        "protocol_result": claim.protocol_result,
        "rationale": claim.rationale,
        "evidence_summary_hash": claim.evidence_summary_hash,
        "supersedes": claim.supersedes,
        "superseded_by": claim.superseded_by,
        "challenge_reason_hash": claim.challenge_reason_hash,
        "created_at": claim.created_at,
        "updated_at": claim.updated_at,
        "scientific_confirmation": False,
    }


def _require_text(value: str, field: str, limit: int) -> str:
    cleaned = value.strip()
    if cleaned == "" or len(cleaned) > limit:
        raise gl.vm.UserError(
            f"{ERROR_EXPECTED} {field} must be 1 to {limit} characters"
        )
    return cleaned


def _require_sha256(value: str, field: str) -> str:
    cleaned = value.strip().lower()
    if not _is_sha256(cleaned):
        raise gl.vm.UserError(f"{ERROR_EXPECTED} {field} must be a lowercase sha256 hex digest")
    return cleaned


def _is_sha256(value: str) -> bool:
    if len(value) != 64:
        return False
    for char in value:
        if char not in "0123456789abcdef":
            return False
    return True


def _require_policy_pair(claim_type: str, policy_version: str) -> tuple[str, str]:
    if claim_type == TYPE_CELESTIAL and policy_version == POLICY_CELESTIAL:
        return claim_type, policy_version
    if claim_type == TYPE_SIGNAL and policy_version == POLICY_SIGNAL:
        return claim_type, policy_version
    raise gl.vm.UserError(
        f"{ERROR_EXPECTED} Unsupported claim_type/policy_version pair"
    )


def _evaluate(summary: str, claim_type: str, policy_version: str) -> tuple[str, str]:
    try:
        document = json.loads(summary)
    except json.JSONDecodeError:
        return RESULT_INSUFFICIENT, "Evidence summary is not valid JSON."
    if not isinstance(document, dict):
        return RESULT_INSUFFICIENT, "Evidence summary must be a JSON object."

    reasons: list[str] = []
    blocking: list[str] = []

    if document.get("claim_type") != claim_type:
        blocking.append("claim_type does not match the registered claim")
    if document.get("policy_version") != policy_version:
        blocking.append("policy_version does not match the registered claim")
    if document.get("schema_version") != "1.1":
        blocking.append("schema_version must be 1.1")

    status = str(document.get("scientific_status", "")).strip().lower()
    if status in CONFIRMATION_CLAIMS:
        blocking.append(
            "scientific_status claims confirmation; this policy cannot certify a discovery"
        )
    elif status not in ALLOWED_SCIENCE:
        reasons.append("scientific_status is missing or not in the allowed vocabulary")

    if claim_type == TYPE_CELESTIAL:
        _review_celestial(document, blocking, reasons)
    else:
        _review_signal(document, blocking, reasons)

    if blocking:
        return RESULT_INSUFFICIENT, _join(blocking + reasons)
    if reasons:
        return RESULT_REVIEW, _join(reasons)
    return (
        RESULT_SUFFICIENT,
        "Required artifacts, provenance, and methodology fields are present. This is not a scientific confirmation.",
    )


def _review_celestial(document: dict, blocking: list[str], reasons: list[str]) -> None:
    target = document.get("target")
    if not isinstance(target, dict) or not str(target.get("id", "")).strip():
        blocking.append("target.id is required")
    elif not _has_coordinate(target, "ra_deg") or not _has_coordinate(target, "dec_deg"):
        blocking.append("target coordinates are required")

    archive = document.get("archive")
    observation_ids = []
    archive_name = ""
    if isinstance(archive, dict):
        archive_name = str(archive.get("name", "")).strip()
        raw_ids = archive.get("observation_ids")
        if isinstance(raw_ids, list):
            observation_ids = [str(item).strip() for item in raw_ids if str(item).strip()]
    if archive_name == "":
        blocking.append("archive.name is required")
    if len(observation_ids) == 0:
        blocking.append("at least one observation id is required")
    elif archive_name not in CELESTIAL_ARCHIVES:
        reasons.append(
            f"archive '{archive_name}' is outside the celestial allowlist, so a person must review provenance"
        )

    _require_analysis(document, reasons)
    if not _has_metric(document, "period"):
        blocking.append("a period metric with a unit is required")
    if not (
        _has_metric(document, "depth")
        or _has_metric(document, "snr")
        or _has_metric(document, "snr_proxy")
    ):
        blocking.append("a depth or signal-to-noise metric is required")
    if not _has_artifact(document):
        blocking.append("at least one artifact sha256 is required")
    _require_cross_matches(document, reasons)
    _require_text_list(document, "limitations", "limitations", reasons)
    tests = document.get("false_positive_tests")
    names = tests if isinstance(tests, list) else []
    if "odd_even" not in names or "secondary_eclipse" not in names:
        reasons.append("odd-even and secondary-eclipse tests must both be documented")


def _review_signal(document: dict, blocking: list[str], reasons: list[str]) -> None:
    signal = document.get("signal")
    if not isinstance(signal, dict):
        blocking.append("signal observation block is required")
        signal = {}
    if not str(signal.get("observation_id", "")).strip():
        blocking.append("signal.observation_id is required")
    for field in ("frequency_range", "time_range", "snr_method", "calibration"):
        if not str(signal.get(field, "")).strip():
            blocking.append(f"signal.{field} is required")
    archive_name = ""
    archive = document.get("archive")
    if isinstance(archive, dict):
        archive_name = str(archive.get("name", "")).strip()
    if archive_name == "":
        blocking.append("archive.name is required")
    elif archive_name not in SIGNAL_ARCHIVES:
        reasons.append(
            f"archive '{archive_name}' is outside the radio allowlist, so a person must review provenance"
        )
    if not _has_artifact(document):
        blocking.append("at least one waterfall or spectrum artifact sha256 is required")
    controls = document.get("rfi_tests")
    if not isinstance(controls, list) or len(controls) == 0:
        blocking.append("at least one RFI exclusion test is required")
    off_target = str(document.get("off_target_comparison", "")).strip().lower()
    if off_target != "present":
        reasons.append("an off-target comparison is not marked present")
    _require_analysis(document, reasons)
    _require_text_list(document, "limitations", "limitations", reasons)


def _require_analysis(document: dict, reasons: list[str]) -> None:
    analysis = document.get("analysis")
    commit = ""
    digest = ""
    if isinstance(analysis, dict):
        commit = str(analysis.get("git_commit", "")).strip()
        digest = str(analysis.get("container_digest", "")).strip()
    if commit == "" or digest == "":
        reasons.append("git commit and container digest are required for reproducibility")


def _require_cross_matches(document: dict, reasons: list[str]) -> None:
    matches = document.get("cross_matches")
    if not isinstance(matches, list) or len(matches) == 0:
        reasons.append("a catalogue cross-match snapshot is required")
        return
    first = matches[0]
    if not isinstance(first, dict) or not str(first.get("catalogue", "")).strip():
        reasons.append("cross-match catalogue name is required")
    elif not str(first.get("query_snapshot_sha256", "")).strip():
        reasons.append("cross-match query snapshot hash is required")


def _require_text_list(document: dict, key: str, label: str, reasons: list[str]) -> None:
    value = document.get(key)
    if isinstance(value, str) and value.strip():
        return
    if isinstance(value, list) and any(str(item).strip() for item in value):
        return
    reasons.append(f"{label} must state what this evidence does not show")


def _has_coordinate(target: dict, key: str) -> bool:
    return _is_number(target.get(key))


def _has_metric(document: dict, name: str) -> bool:
    metrics = document.get("metrics")
    if not isinstance(metrics, list):
        return False
    for metric in metrics:
        if not isinstance(metric, dict):
            continue
        if str(metric.get("name", "")).strip() != name:
            continue
        if not str(metric.get("unit", "")).strip():
            continue
        if _is_number(metric.get("value")):
            return True
    return False


def _has_artifact(document: dict) -> bool:
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    for artifact in artifacts:
        if isinstance(artifact, dict) and _is_sha256(str(artifact.get("sha256", "")).strip().lower()):
            return True
    return False


def _is_number(value) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, str):
        return _numeric_text(value.strip())
    return type(value).__name__ == "float"


def _numeric_text(value: str) -> bool:
    if value == "" or value in ("+", "-", ".", "+.", "-."):
        return False
    seen_dot = False
    seen_digit = False
    for index, char in enumerate(value):
        if char in "+-" and index == 0:
            continue
        if char == "." and not seen_dot:
            seen_dot = True
            continue
        if char in "0123456789":
            seen_digit = True
            continue
        return False
    return seen_digit


def _join(parts: list[str]) -> str:
    text = "; ".join(parts)
    if len(text) <= MAX_RATIONALE_CHARS:
        return text
    return text[: MAX_RATIONALE_CHARS - 3] + "..."
