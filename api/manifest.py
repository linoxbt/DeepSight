"""Canonical evidence manifests, schema 1.1."""

from __future__ import annotations

import hashlib
import json
from typing import Any


SYNTHETIC_ARCHIVE = "DeepSight synthetic calibration"


def canonicalize(document: dict[str, Any]) -> str:
    return json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_manifest(
    *,
    target: dict[str, Any],
    fit: dict[str, Any],
    series_sha256: str,
    analysis_id: str,
    claimant_address: str,
    researcher_address: str,
    cross_match: dict[str, Any],
    snapshot_sha256: str,
    git_commit: str,
    environment_sha256: str = "",
    diagnostics: list | None = None,
    quality_flags: list | None = None,
) -> dict[str, Any]:
    limitations = [
        "Not scientifically confirmed",
        "Period uncertainty is a conditional white-noise bootstrap; aliases and systematic noise are not included",
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
        "claimant_address": claimant_address,
        "researcher_address": researcher_address,
        "claim_type": "celestial_object_evidence",
        "policy_version": "celestial-v5",
        "target": {
            "id": target["id"],
            "ra_deg": target["ra_deg"],
            "dec_deg": target["dec_deg"],
            "frame": "ICRS",
        },
        "archive": {
            "name": SYNTHETIC_ARCHIVE if target["synthetic"] else target["archive"],
            "observation_ids": [target["observation_id"]],
            "raw_source_sha256": target.get("raw_sha256") if not target["synthetic"] else None,
            "raw_source_uri": target.get("raw_uri") if not target["synthetic"] else None,
        },
        "analysis": {
            "git_commit": git_commit,
            "container_digest": "",
            "environment_sha256": environment_sha256,
            "environment_uri": f"/v1/artifacts/{environment_sha256}",
            "parameters": {"period_min_days": 0.7, "period_max_days": 12.0, "n_periods": 700},
            "pipeline": "bls-numpy-v1",
            "pipeline_version": "1",
        },
        "metrics": [
            {
                "name": "period",
                "value": round(fit["period_days"], 6),
                "unit": "d",
                "uncertainty": fit.get("period_uncertainty_days"),
                "uncertainty_method": "residual_bootstrap_white_noise_v1" if fit.get("period_uncertainty_days") is not None else "unavailable",
                "grid_resolution_days": fit.get("period_resolution_days"),
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
                "uri": f"/v1/artifacts/{series_sha256}",
                "kind": "light_curve",
            }
        ],
        "cross_matches": [
            {
                "catalogue": cross_match["catalogue"],
                "result": cross_match["result"],
                "query_snapshot_sha256": snapshot_sha256,
                "uri": f"/v1/artifacts/{snapshot_sha256}",
                "live_query": bool(cross_match.get("live_query")),
            }
        ],
        "false_positive_tests": ["odd_even", "secondary_eclipse"],
        "diagnostics": diagnostics or [],
        "quality_flags": quality_flags or [],
        "limitations": limitations,
        "scientific_status": science,
    }
