"""Canonical evidence manifests, schema 1.1."""

from __future__ import annotations

import hashlib
import json
from typing import Any


SYNTHETIC_ARCHIVE = "DeepSight synthetic calibration"


def canonicalize(document: dict[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    target: dict[str, Any],
    fit: dict[str, Any],
    series_sha256: str,
    analysis_id: str,
    cross_match: dict[str, Any],
    snapshot_sha256: str,
    git_commit: str,
) -> dict[str, Any]:
    limitations = [
        "Not scientifically confirmed",
        "The signal-to-noise figure is a white-noise proxy, not a CDPP",
    ]
    if cross_match["result"] == "no_exact_match":
        limitations.append("A catalogue non-match is not evidence of a new object")
    if target["synthetic"]:
        limitations.append("The light curve is a local synthetic injection, not an archive product")
    else:
        limitations.append(
            f"TESS SPOC PDCSAP flux from sector {target.get('sector', '?')}. One sector, quality flag 0 only."
        )
    if cross_match["result"] == "period_coincidence":
        limitations.append(cross_match["note"])
    if cross_match["result"] == "known_object":
        limitations.append(f"{cross_match['note']} The protocol does not reconfirm the planet.")
    science = "known_object" if cross_match["result"] == "known_object" else "unconfirmed_candidate"

    return {
        "schema_version": "1.1",
        "claim_type": "celestial_object_evidence",
        "policy_version": "celestial-v1",
        "target": {
            "id": target["id"],
            "ra_deg": target["ra_deg"],
            "dec_deg": target["dec_deg"],
            "frame": "ICRS",
        },
        "archive": {
            "name": SYNTHETIC_ARCHIVE if target["synthetic"] else target["archive"],
            "observation_ids": [target["observation_id"]],
        },
        "analysis": {
            "git_commit": git_commit,
            "container_digest": "local-dev",
            "pipeline": "bls-numpy-v1",
            "pipeline_version": "1",
        },
        "metrics": [
            {
                "name": "period",
                "value": round(fit["period_days"], 6),
                "unit": "d",
                "uncertainty": round(fit["period_uncertainty_days"], 6),
            },
            {
                "name": "depth",
                "value": round(fit["depth"], 6),
                "unit": "relative_flux",
                "uncertainty": None,
            },
            {
                "name": "snr_proxy",
                "value": round(fit["snr_proxy"], 3),
                "unit": "1",
                "uncertainty": None,
            },
            {
                "name": "duration",
                "value": round(fit["duration_days"], 6),
                "unit": "d",
                "uncertainty": None,
            },
        ],
        "artifacts": [
            {
                "sha256": series_sha256,
                "uri": f"local://analyses/{analysis_id}/series",
                "kind": "light_curve",
            }
        ],
        "cross_matches": [
            {
                "catalogue": cross_match["catalogue"],
                "result": cross_match["result"],
                "query_snapshot_sha256": snapshot_sha256,
                "live_query": bool(cross_match.get("live_query")),
            }
        ],
        "false_positive_tests": ["odd_even", "secondary_eclipse"],
        "limitations": limitations,
        "scientific_status": science,
    }
