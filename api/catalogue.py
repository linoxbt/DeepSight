"""Small local cross-match extract.

This is not a live query of the NASA Exoplanet Archive. Period coincidence
against this list is a warning, not an identification.
"""

from __future__ import annotations

REFERENCE_CATALOGUE = [
    {
        "name": "Pi Men c",
        "host_tic": "261136679",
        "period_days": 6.2679,
        "ra_deg": 84.2912,
        "dec_deg": -80.4691,
        "catalogue": "NASA Exoplanet Archive",
    },
    {
        "name": "AU Mic b",
        "host_tic": "441420236",
        "period_days": 8.46321,
        "ra_deg": 311.2897,
        "dec_deg": -31.3409,
        "catalogue": "NASA Exoplanet Archive",
    },
    {
        "name": "TOI-270 b",
        "host_tic": "259377017",
        "period_days": 3.35992,
        "ra_deg": 68.7664,
        "dec_deg": -51.9496,
        "catalogue": "NASA Exoplanet Archive",
    },
    {
        "name": "TOI-270 c",
        "host_tic": "259377017",
        "period_days": 5.66051,
        "ra_deg": 68.7664,
        "dec_deg": -51.9496,
        "catalogue": "NASA Exoplanet Archive",
    },
    {
        "name": "TOI-270 d",
        "host_tic": "259377017",
        "period_days": 11.38194,
        "ra_deg": 68.7664,
        "dec_deg": -51.9496,
        "catalogue": "NASA Exoplanet Archive",
    },
    {
        "name": "HD 219134 b",
        "host_tic": "283722336",
        "period_days": 3.092926,
        "ra_deg": 348.3208,
        "dec_deg": 57.1684,
        "catalogue": "NASA Exoplanet Archive",
    },
    {
        "name": "LHS 1140 b",
        "host_tic": "92226327",
        "period_days": 24.736959,
        "ra_deg": 11.4792,
        "dec_deg": -15.2715,
        "catalogue": "NASA Exoplanet Archive",
    },
]

CATALOGUE_VERSION = "deepsight-local-extract-2026-10-14"


def cross_match(target_id: str, period_days: float, tic: str | None = None) -> dict:
    identifiers = {target_id, target_id.removeprefix("TIC-"), target_id.removeprefix("TIC ")}
    if tic:
        identifiers.add(tic)
    period_hits = []
    id_hits = []
    for row in REFERENCE_CATALOGUE:
        tolerance = max(0.02, abs(row["period_days"]) * 0.005)
        if abs(period_days - row["period_days"]) <= tolerance:
            period_hits.append(row)
        if row["host_tic"] in identifiers or row["name"] in identifiers:
            id_hits.append(row)

    if id_hits and period_hits and any(row in period_hits for row in id_hits):
        matched = next(row for row in id_hits if row in period_hits)
        result = "known_object"
        note = f"Target id and period agree with {matched['name']} in the local extract."
    elif period_hits:
        names = ", ".join(row["name"] for row in period_hits)
        result = "period_coincidence"
        note = (
            f"Recovered period is close to {names}. The target identifier does not match. "
            "This is not an identification."
        )
    elif id_hits:
        names = ", ".join(row["name"] for row in id_hits)
        result = "id_match_period_differs"
        note = f"Target id matches {names}, but the recovered period does not."
    else:
        result = "no_exact_match"
        note = "No id or period match in the local extract. A non-match is not evidence of a new planet."

    return {
        "catalogue": "NASA Exoplanet Archive",
        "catalogue_version": CATALOGUE_VERSION,
        "live_query": False,
        "result": result,
        "note": note,
        "period_days": round(period_days, 6),
        "matches": [
            {"name": row["name"], "host_tic": row["host_tic"], "period_days": row["period_days"]}
            for row in (period_hits or id_hits)
        ],
    }
