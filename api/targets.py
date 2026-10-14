"""Runnable calibration targets.

Both series are generated locally. They are labeled synthetic so a policy
review cannot treat them as MAST observations.
"""

from __future__ import annotations

TARGETS = [
    {
        "id": "DS-SYN-001",
        "name": "Calibration transit A",
        "synthetic": True,
        "archive": "DeepSight synthetic calibration",
        "observation_id": "DS-SYN-001-sector-sim",
        "ra_deg": 120.5,
        "dec_deg": -30.2,
        "injected_period_days": 2.507,
        "injected_depth": 0.0084,
        "injected_duration_days": 0.11,
        "seed": 261136679,
        "summary": "A 27.4-day series with one injected box transit. No local catalogue id matches this target.",
    },
    {
        "id": "DS-SYN-002",
        "name": "Period-coincidence control",
        "synthetic": True,
        "archive": "DeepSight synthetic calibration",
        "observation_id": "DS-SYN-002-sector-sim",
        "ra_deg": 210.0,
        "dec_deg": 15.4,
        "injected_period_days": 6.2679,
        "injected_depth": 0.0062,
        "injected_duration_days": 0.11,
        "seed": 441420236,
        "summary": "Injected near the local Pi Men c period. The target id is not Pi Men c, so a period hit must stay a coincidence.",
    },
]


def get_target(target_id: str) -> dict | None:
    for target in TARGETS:
        if target["id"] == target_id:
            return target
    return None
