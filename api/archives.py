"""Live archive clients.

NASA Exoplanet Archive TAP, ESA Gaia DR3 TAP, and JPL Horizons are queried
over their public HTTP APIs. A failed call stays a failure. It is not replaced
with a pretended observation.
"""

from __future__ import annotations

import math
import os
from typing import Any

import httpx

from api.catalogue import CATALOGUE_VERSION, cross_match

TAP_URL = "https://exoplanetarchive.ipac.caltech.edu/TAP/sync"
GAIA_URL = "https://gea.esac.esa.int/tap-server/tap/sync"
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
USER_AGENT = "DeepSight/0.1"


class ArchiveError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def live_tap_enabled() -> bool:
    return os.environ.get("DEEPSIGHT_LIVE_TAP", "1") != "0"


def resolve_cross_match(
    target_id: str,
    period_days: float,
    tic: str | None = None,
    ra: float | None = None,
    dec: float | None = None,
    hostname: str | None = None,
) -> dict[str, Any]:
    local = cross_match(target_id, period_days, tic=tic)
    if not live_tap_enabled():
        return local
    try:
        rows = fetch_planets(tic=tic, hostname=hostname, ra_deg=ra, dec_deg=dec)
    except ArchiveError as exc:
        local["note"] = f"{local['note']} Live TAP did not answer ({exc}). The local extract was used."
        local["live_query"] = False
        return local
    if not rows:
        local["live_query"] = True
        local["tap_rows"] = []
        local["catalogue_version"] = f"nasa-tap-pscomppars+{CATALOGUE_VERSION}"
        local["note"] = (
            f"{local['note']} Live TAP returned no rows for this identifier and coordinate box."
        )
        return local
    matched = _match_rows(rows, target_id, period_days, tic, queried_by_id=bool(tic or hostname))
    matched["tap_rows"] = [
        {"name": row["name"], "period_days": row["period_days"], "tic_id": row["tic_id"]} for row in rows
    ]
    return matched


def fetch_planets(
    *,
    tic: str | None = None,
    hostname: str | None = None,
    ra_deg: float | None = None,
    dec_deg: float | None = None,
    radius_deg: float = 0.02,
) -> list[dict[str, Any]]:
    where = _planet_where(tic=tic, hostname=hostname, ra_deg=ra_deg, dec_deg=dec_deg, radius_deg=radius_deg)
    if where is None:
        raise ArchiveError("Provide a TIC id, a host name, or coordinates.", 422)
    rows = _tap_rows(where)
    if rows or not tic or ra_deg is None or dec_deg is None:
        return rows
    cone = _planet_where(ra_deg=ra_deg, dec_deg=dec_deg, radius_deg=radius_deg)
    return _tap_rows(cone) if cone else rows


def query_gaia(ra_deg: float, dec_deg: float, radius_arcsec: float = 36) -> dict[str, Any]:
    ra = _coordinate(ra_deg, "ra_deg", -360, 360)
    dec = _coordinate(dec_deg, "dec_deg", -90, 90)
    radius = _coordinate(radius_arcsec, "radius_arcsec", 1, 120)
    radius_deg = radius / 3600.0
    query = (
        "SELECT TOP 8 source_id,ra,dec,parallax,phot_g_mean_mag "
        "FROM gaiadr3.gaia_source WHERE 1=CONTAINS(POINT('ICRS',ra,dec),"
        f"CIRCLE('ICRS',{ra:.8f},{dec:.8f},{radius_deg:.8f}))"
    )
    payload = _post_form(
        GAIA_URL,
        {"REQUEST": "doQuery", "LANG": "ADQL", "FORMAT": "json", "QUERY": query},
        timeout=50,
    )
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ArchiveError("Gaia TAP did not return a table.")
    names = [str(column.get("name", "")) for column in payload.get("metadata") or []]
    sources = []
    for record in payload["data"]:
        if not isinstance(record, list):
            continue
        values = {names[index]: record[index] for index in range(min(len(names), len(record)))}
        source_ra = _optional_float(values.get("ra"))
        source_dec = _optional_float(values.get("dec"))
        sources.append(
            {
                "source_id": str(values.get("source_id", "")),
                "ra_deg": source_ra,
                "dec_deg": source_dec,
                "parallax_mas": _optional_float(values.get("parallax")),
                "phot_g_mean_mag": _optional_float(values.get("phot_g_mean_mag")),
                "separation_arcsec": None
                if source_ra is None or source_dec is None
                else round(_separation_arcsec(ra, dec, source_ra, source_dec), 2),
            }
        )
    sources.sort(key=lambda item: item["separation_arcsec"] if item["separation_arcsec"] is not None else 1e9)
    return {
        "live_query": True,
        "service": "ESA Gaia DR3 TAP",
        "ra_deg": ra,
        "dec_deg": dec,
        "radius_arcsec": radius,
        "sources": sources,
        "note": "A nearby Gaia source is a position match. It is not a planet identification.",
    }


def query_horizons(command: str) -> dict[str, Any]:
    cleaned = " ".join(command.strip().split())
    if not cleaned or len(cleaned) > 48 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .+_-" for char in cleaned):
        raise ArchiveError("Use a Horizons name or NAIF id, for example 499 or Voyager 1.", 422)
    from datetime import date, timedelta

    start = date.today()
    stop = start + timedelta(days=1)
    payload = _get_json(
        HORIZONS_URL,
        {
            "format": "json",
            "COMMAND": cleaned,
            "OBJ_DATA": "YES",
            "MAKE_EPHEM": "YES",
            "EPHEM_TYPE": "OBSERVER",
            "CENTER": "500@399",
            "START_TIME": start.isoformat(),
            "STOP_TIME": stop.isoformat(),
            "STEP_SIZE": "1 d",
        },
        timeout=40,
    )
    text = str(payload.get("result", "")) if isinstance(payload, dict) else ""
    if not text:
        raise ArchiveError("JPL Horizons returned an empty result.")
    found = "No matches found" not in text and "matching small-bodies" not in text.lower()
    ephemeris = _ephemeris_lines(text)
    if "No matches found" in text:
        found = False
    return {
        "live_query": True,
        "service": "JPL Horizons",
        "command": cleaned,
        "found": found and bool(ephemeris or "Revised:" in text or "Spacecraft" in text or "PHYSICAL DATA" in text),
        "ephemeris": ephemeris,
        "excerpt": text[:1200],
        "note": (
            "Horizons returned an observer ephemeris. That is not a transit detection."
            if found
            else "Horizons has no unique match for that command. Stars such as TOI-270 are often absent; try a NAIF id such as 499 or -31."
        ),
    }


def _planet_where(
    *,
    tic: str | None = None,
    hostname: str | None = None,
    ra_deg: float | None = None,
    dec_deg: float | None = None,
    radius_deg: float = 0.02,
) -> str | None:
    if tic:
        label = _tic_digits(tic)
        return f"tic_id = 'TIC {label}'"
    if hostname:
        name = _hostname(hostname)
        return f"hostname = '{name}'"
    if ra_deg is not None and dec_deg is not None:
        ra = _coordinate(ra_deg, "ra_deg", 0, 360)
        dec = _coordinate(dec_deg, "dec_deg", -90, 90)
        radius = _coordinate(radius_deg, "radius_deg", 0.0001, 1)
        return (
            f"ra BETWEEN {ra - radius:.6f} AND {ra + radius:.6f} "
            f"AND dec BETWEEN {dec - radius:.6f} AND {dec + radius:.6f}"
        )
    return None


def _tap_rows(where: str) -> list[dict[str, Any]]:
    query = (
        "SELECT TOP 30 pl_name,hostname,pl_orbper,ra,dec,tic_id "
        f"FROM pscomppars WHERE {where}"
    )
    payload = _get_json(TAP_URL, {"query": query, "format": "json"}, timeout=30)
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error") or "NASA TAP rejected the query."
        raise ArchiveError(str(message))
    if not isinstance(payload, list):
        raise ArchiveError("NASA TAP did not return a row list.")
    rows = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        name = str(item.get("pl_name", "")).strip()
        period = _optional_float(item.get("pl_orbper"))
        if not name or period is None or name in seen:
            continue
        seen.add(name)
        tic_id = str(item.get("tic_id") or "").strip()
        digits = "".join(character for character in tic_id if character.isdigit())
        rows.append(
            {
                "name": name,
                "hostname": str(item.get("hostname") or "").strip(),
                "period_days": period,
                "ra_deg": _optional_float(item.get("ra")),
                "dec_deg": _optional_float(item.get("dec")),
                "tic_id": tic_id,
                "host_tic": str(int(digits)) if digits else "",
            }
        )
    return rows


def _match_rows(
    rows: list[dict[str, Any]],
    target_id: str,
    period_days: float,
    tic: str | None,
    queried_by_id: bool,
) -> dict[str, Any]:
    identifiers = {target_id, target_id.removeprefix("TIC-"), target_id.removeprefix("TIC ")}
    if tic:
        digits = _tic_digits(tic)
        identifiers.update({digits, f"TIC {digits}", f"TIC-{digits}"})
    period_hits = []
    id_hits = []
    for row in rows:
        tolerance = max(0.02, abs(row["period_days"]) * 0.005)
        if abs(period_days - row["period_days"]) <= tolerance:
            period_hits.append(row)
        labels = {row["name"], row["hostname"], row["tic_id"], row["host_tic"], f"TIC-{row['host_tic']}"}
        # A TIC lookup may fall back to a coordinate cone. A nearby row is not
        # an identifier match merely because the original request had a TIC.
        if identifiers.intersection(labels):
            id_hits.append(row)
    if id_hits and period_hits and any(row in period_hits for row in id_hits):
        matched = next(row for row in id_hits if row in period_hits)
        result = "known_object"
        note = (
            f"Target id and period agree with {matched['name']} in the NASA Exoplanet Archive TAP (pscomppars)."
        )
    elif period_hits and not id_hits:
        names = ", ".join(row["name"] for row in period_hits)
        result = "period_coincidence"
        note = (
            f"Recovered period is close to {names} in the live TAP response. "
            "The target identifier does not match. This is not an identification."
        )
    elif id_hits:
        names = ", ".join(row["name"] for row in id_hits)
        result = "id_match_period_differs"
        note = f"Live TAP lists {names} for this target, but the recovered period does not agree."
    else:
        result = "no_exact_match"
        note = "Live TAP returned rows, and none match this identifier and period. A non-match is not a new planet."
    return {
        "catalogue": "NASA Exoplanet Archive",
        "catalogue_version": "nasa-tap-pscomppars",
        "live_query": True,
        "result": result,
        "note": note,
        "period_days": round(period_days, 6),
        "matches": [
            {"name": row["name"], "host_tic": row["host_tic"], "period_days": row["period_days"]}
            for row in (period_hits or id_hits)
        ],
    }


def _tic_digits(value: str) -> str:
    digits = "".join(character for character in str(value) if character.isdigit())
    if not digits or len(digits) > 12:
        raise ArchiveError("Enter a numeric TIC id, for example 259377017.", 422)
    return str(int(digits))


def _hostname(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .+-")
    if not cleaned or len(cleaned) > 40 or any(character not in allowed for character in cleaned):
        raise ArchiveError("Host name contains characters the TAP query will not accept.", 422)
    return cleaned.replace("'", "")


def _coordinate(value: float, name: str, low: float, high: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ArchiveError(f"{name} must be a number.", 422) from exc
    if not math.isfinite(number) or number < low or number > high:
        raise ArchiveError(f"{name} is outside {low} to {high}.", 422)
    return number


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _separation_arcsec(ra_a: float, dec_a: float, ra_b: float, dec_b: float) -> float:
    scale = math.cos(math.radians((dec_a + dec_b) / 2.0))
    return math.hypot((ra_a - ra_b) * scale, dec_a - dec_b) * 3600.0


def _ephemeris_lines(text: str) -> list[str]:
    if "$$SOE" not in text or "$$EOE" not in text:
        return []
    block = text.split("$$SOE", 1)[1].split("$$EOE", 1)[0]
    return [line.strip() for line in block.splitlines() if line.strip()][:2]


def _get_json(url: str, params: dict[str, str], timeout: float) -> Any:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, params=params, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise ArchiveError(f"The archive did not answer ({url.split('/')[2]}).") from exc
    except ValueError as exc:
        raise ArchiveError(f"The archive returned data that is not JSON ({url.split('/')[2]}).") from exc


def _post_form(url: str, data: dict[str, str], timeout: float) -> Any:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.post(url, data=data, headers={"User-Agent": USER_AGENT})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as exc:
        raise ArchiveError(f"The archive did not answer ({url.split('/')[2]}).") from exc
    except ValueError as exc:
        raise ArchiveError(f"The archive returned data that is not JSON ({url.split('/')[2]}).") from exc
