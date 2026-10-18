"""Off-chain mirror of the Proof of Discovery policy.

The intelligent contract in contracts/proof_of_discovery.py is the consensus
copy. Keep the vocabulary and the sufficiency rules aligned with it.
"""

from __future__ import annotations

import json
from typing import Any

RESULT_SUFFICIENT = "EVIDENCE_SUFFICIENT"
RESULT_INSUFFICIENT = "EVIDENCE_INSUFFICIENT"
RESULT_REVIEW = "NEEDS_HUMAN_REVIEW"

POLICY_CELESTIAL = "celestial-v3"
POLICY_SIGNAL = "signal-v3"
TYPE_CELESTIAL = "celestial_object_evidence"
TYPE_SIGNAL = "radio_signal_integrity"

CELESTIAL_ARCHIVES = {"MAST", "NASA Exoplanet Archive", "Gaia", "JPL Horizons"}
SIGNAL_ARCHIVES = {"Breakthrough Listen"}
ALLOWED_SCIENCE = {
    "unconfirmed_candidate",
    "known_object",
    "artifact",
    "inconclusive",
}
CONFIRMATION_CLAIMS = {
    "confirmed",
    "planet_confirmed",
    "confirmed_planet",
    "alien_confirmed",
    "extraterrestrial",
    "technosignature",
    "verified_discovery",
    "discovery_confirmed",
}


def evaluate(summary: str, claim_type: str, policy_version: str, target_id: str = "") -> tuple[str, str]:
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
    if not _valid_address(document.get("claimant_address")) or not _valid_address(document.get("researcher_address")):
        blocking.append("claimant and researcher wallet addresses are required")
    if target_id and (not isinstance(document.get("target"), dict) or document["target"].get("id") != target_id):
        blocking.append("target.id does not match the registered target")

    status = str(document.get("scientific_status", "")).strip().lower()
    if status in CONFIRMATION_CLAIMS:
        blocking.append(
            "scientific_status claims confirmation; this policy cannot certify a discovery"
        )
    elif status not in ALLOWED_SCIENCE:
        reasons.append("scientific_status is missing or not in the allowed vocabulary")

    if claim_type == TYPE_CELESTIAL:
        _review_celestial(document, blocking, reasons)
    elif claim_type == TYPE_SIGNAL:
        _review_signal(document, blocking, reasons)
    else:
        blocking.append("claim_type is not supported")

    if blocking:
        return RESULT_INSUFFICIENT, _join(blocking + reasons)
    if claim_type == TYPE_SIGNAL:
        reasons.append("Radio measurements and RFI controls have no independent archive comparison.")
    else:
        reasons.append("Independent archive comparison required for measured period and depth.")
    if reasons:
        return RESULT_REVIEW, _join(reasons)
    return (
        RESULT_SUFFICIENT,
        "Required artifacts, provenance, and methodology fields are present. This is not a scientific confirmation.",
    )


def _review_celestial(document: dict[str, Any], blocking: list[str], reasons: list[str]) -> None:
    target = document.get("target")
    if not isinstance(target, dict) or not str(target.get("id", "")).strip():
        blocking.append("target.id is required")
    elif not _in_range(target.get("ra_deg"), 0, 360, True) or not _in_range(target.get("dec_deg"), -90, 90):
        blocking.append("valid ICRS coordinates are required")

    archive = document.get("archive") if isinstance(document.get("archive"), dict) else {}
    archive_name = str(archive.get("name", "")).strip()
    raw_ids = archive.get("observation_ids")
    observation_ids = [str(item).strip() for item in raw_ids if str(item).strip()] if isinstance(raw_ids, list) else []
    if archive_name == "":
        blocking.append("archive.name is required")
    if not observation_ids:
        blocking.append("at least one observation id is required")
    elif archive_name not in CELESTIAL_ARCHIVES:
        reasons.append(
            f"archive '{archive_name}' is outside the celestial allowlist, so a person must review provenance"
        )

    _require_analysis(document, reasons)
    if not _has_metric(document, "period"):
        blocking.append("a period metric with a unit is required")
    elif not _positive_uncertainty(document, "period"):
        reasons.append("period uncertainty with a stated method is required")
    if not (_has_metric(document, "depth") or _has_metric(document, "snr") or _has_metric(document, "snr_proxy")):
        blocking.append("a depth or signal-to-noise metric is required")
    if not _has_artifact(document):
        blocking.append("at least one artifact sha256 is required")
    _require_cross_matches(document, reasons)
    _require_limitations(document, reasons)
    tests = document.get("false_positive_tests")
    names = tests if isinstance(tests, list) else []
    if "odd_even" not in names or "secondary_eclipse" not in names:
        reasons.append("odd-even and secondary-eclipse tests must both be documented")
    flags = document.get("quality_flags")
    if isinstance(flags, list) and any(isinstance(flag, dict) and flag.get("severity") in ("warning", "error") for flag in flags):
        reasons.append("analysis quality warnings require independent human review")


def _review_signal(document: dict[str, Any], blocking: list[str], reasons: list[str]) -> None:
    signal = document.get("signal") if isinstance(document.get("signal"), dict) else {}
    if not document.get("signal"):
        blocking.append("signal observation block is required")
    if not str(signal.get("observation_id", "")).strip():
        blocking.append("signal.observation_id is required")
    for field in ("frequency_range", "time_range", "snr_method", "calibration"):
        if not str(signal.get(field, "")).strip():
            blocking.append(f"signal.{field} is required")
    archive = document.get("archive") if isinstance(document.get("archive"), dict) else {}
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
    if str(document.get("off_target_comparison", "")).strip().lower() != "present":
        reasons.append("an off-target comparison is not marked present")
    _require_analysis(document, reasons)
    _require_limitations(document, reasons)


def _require_analysis(document: dict[str, Any], reasons: list[str]) -> None:
    analysis = document.get("analysis") if isinstance(document.get("analysis"), dict) else {}
    if not str(analysis.get("git_commit", "")).strip() or not ((str(analysis.get("container_digest", "")).startswith("sha256:") and _valid_digest(str(analysis.get("container_digest", ""))[7:])) or _valid_digest(analysis.get("environment_sha256", ""))):
        reasons.append("git commit and environment checksum or container digest are required for reproducibility")


def _require_cross_matches(document: dict[str, Any], reasons: list[str]) -> None:
    matches = document.get("cross_matches")
    if not isinstance(matches, list) or len(matches) == 0:
        reasons.append("a catalogue cross-match snapshot is required")
        return
    first = matches[0]
    if not isinstance(first, dict) or not str(first.get("catalogue", "")).strip():
        reasons.append("cross-match catalogue name is required")
    elif not _valid_digest(first.get("query_snapshot_sha256", "")):
        reasons.append("valid cross-match query snapshot hash is required")


def _require_limitations(document: dict[str, Any], reasons: list[str]) -> None:
    value = document.get("limitations")
    if isinstance(value, str) and value.strip():
        return
    if isinstance(value, list) and any(str(item).strip() for item in value):
        return
    reasons.append("limitations must state what this evidence does not show")


def _has_metric(document: dict[str, Any], name: str) -> bool:
    metrics = document.get("metrics")
    if not isinstance(metrics, list):
        return False
    for metric in metrics:
        if not isinstance(metric, dict) or str(metric.get("name", "")).strip() != name:
            continue
        if _metric_valid(metric, name):
            return True
    return False


def _has_artifact(document: dict[str, Any]) -> bool:
    artifacts = document.get("artifacts")
    if not isinstance(artifacts, list):
        return False
    for artifact in artifacts:
        digest = str(artifact.get("sha256", "")).strip().lower() if isinstance(artifact, dict) else ""
        if len(digest) == 64 and all(char in "0123456789abcdef" for char in digest):
            return True
    return False


def _positive_uncertainty(document: dict[str, Any], name: str) -> bool:
    for metric in document.get("metrics", []):
        if isinstance(metric, dict) and metric.get("name") == name:
            pair = _ratio(metric.get("uncertainty"))
            return bool(pair and pair[0] > 0 and str(metric.get("uncertainty_method", "")).strip())
    return False


def _ratio(value):
    if isinstance(value, bool) or value is None:
        return None
    text = str(value).strip().lower()
    if not text or len(text) > 100:
        return None
    exponent = 0
    if "e" in text:
        parts = text.split("e")
        if len(parts) != 2:
            return None
        exponent_text = parts[1][1:] if parts[1].startswith(("+", "-")) else parts[1]
        if not exponent_text or any(c not in "0123456789" for c in exponent_text) or len(exponent_text) > 3:
            return None
        exponent = int(parts[1])
        if exponent < -100 or exponent > 100:
            return None
        text = parts[0]
    sign = -1 if text.startswith("-") else 1
    if text.startswith(("-", "+")):
        text = text[1:]
    parts = text.split(".")
    if len(parts) > 2:
        return None
    digits = "".join(parts)
    if not digits or any(c not in "0123456789" for c in digits):
        return None
    scale = len(parts[1]) if len(parts) == 2 else 0
    numerator = sign * int(digits)
    denominator = 10 ** scale
    if exponent >= 0:
        numerator *= 10 ** exponent
    else:
        denominator *= 10 ** (-exponent)
    return numerator, denominator


def _is_number(value) -> bool:
    return _ratio(value) is not None


def _in_range(value, low: int, high: int, exclusive_high: bool = False) -> bool:
    pair = _ratio(value)
    if pair is None:
        return False
    numerator, denominator = pair
    return numerator >= low * denominator and (numerator < high * denominator if exclusive_high else numerator <= high * denominator)


def _valid_digest(value) -> bool:
    text = str(value)
    return len(text) == 64 and all(c in "0123456789abcdef" for c in text)


def _valid_address(value) -> bool:
    text = str(value).lower()
    return len(text) == 42 and text.startswith("0x") and all(c in "0123456789abcdef" for c in text[2:])


def _join(parts: list[str]) -> str:
    text = "; ".join(parts)
    return text if len(text) <= 600 else text[:597] + "..."


def _metric_valid(metric: dict, name: str) -> bool:
    pair = _ratio(metric.get("value"))
    if pair is None:
        return False
    numerator, denominator = pair
    if name == "period":
        return numerator > 0 and metric.get("unit") == "d"
    if name == "depth":
        return 0 < numerator < denominator and metric.get("unit") == "relative_flux"
    if name in ("snr", "snr_proxy"):
        return numerator >= 0 and metric.get("unit") in ("1", "mad")
    return bool(str(metric.get("unit", "")).strip())
