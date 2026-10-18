"""Import one TESS SPOC light curve from MAST.

The adapter downloads a single sector product. It does not search the whole
archive and it does not re-reduce the pixels.
"""

from __future__ import annotations

import json
import secrets
from pathlib import Path
from urllib.parse import quote

import httpx
import numpy as np
from astropy.io import fits

MAST_INVOKE = "https://mast.stsci.edu/api/v0/invoke"
MAST_DOWNLOAD = "https://mast.stsci.edu/api/v0.1/Download/file?uri="
USER_AGENT = "DeepSight/0.1 (local research workspace)"
# Longer cadences first so a sector stays a few megabytes.
EXPOSURE_PREFERENCE = (120, 200, 600, 1800, 20)
MAX_LIGHT_CURVE_BYTES = 64 * 1024 * 1024


class MastError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def normalize_tic(value: str) -> str:
    text = value.strip().upper().replace("TIC", "").replace("-", "").replace(" ", "")
    if not text.isdigit() or not 1 <= len(text) <= 12:
        raise MastError("Enter a numeric TIC id, for example 259377017.", 422)
    return str(int(text))


def fetch_tess_light_curve(tic: str, cache_dir: Path) -> dict:
    tic = normalize_tic(tic)
    cache_dir.mkdir(parents=True, exist_ok=True)
    observation = _choose_observation(_invoke({
        "service": "Mast.Caom.Filtered",
        "format": "json",
        "params": {
            "columns": "obsid,target_name,obs_collection,t_exptime,instrument_name",
            "filters": [
                {"paramName": "target_name", "values": [tic]},
                {"paramName": "obs_collection", "values": ["TESS"]},
                {"paramName": "dataproduct_type", "values": ["timeseries"]},
            ],
        },
    }))
    products = _invoke({
        "service": "Mast.Caom.Products",
        "format": "json",
        "params": {"obsid": observation["obsid"]},
    })
    product = _choose_light_curve(products)
    filename = str(product["productFilename"])
    path = cache_dir / f"{tic}-{filename}"
    if not path.exists() or path.stat().st_size < 1000:
        _download(str(product["dataURI"]), path)
    try:
        curve = read_spoc_light_curve(path)
    except MastError:
        path.unlink(missing_ok=True)
        raise
    if curve["tic"] != tic:
        raise MastError(f"Downloaded file is TIC {curve['tic']}, not {tic}.", 502)
    curve["exposure_seconds"] = int(observation.get("t_exptime") or 0)
    curve["product_filename"] = filename
    curve["data_uri"] = str(product["dataURI"])
    curve["raw_path"] = str(path)
    return curve


def read_spoc_light_curve(path: Path) -> dict:
    with fits.open(path) as hdul:
        header = hdul[0].header
        table = hdul[1].data
        names = set(table.names)
        if "TIME" not in names or "PDCSAP_FLUX" not in names:
            raise MastError("MAST file has no PDCSAP light curve.", 502)
        time = np.array(table["TIME"], dtype=float)
        flux = np.array(table["PDCSAP_FLUX"], dtype=float)
        quality = np.array(table["QUALITY"], dtype=int) if "QUALITY" in names else np.zeros(time.shape, dtype=int)
        sector = int(header.get("SECTOR") or 0)
        tic = str(int(header.get("TICID") or 0))
        ra = float(header.get("RA_OBJ") or 0)
        dec = float(header.get("DEC_OBJ") or 0)
    good = np.isfinite(time) & np.isfinite(flux) & (quality == 0)
    if int(np.count_nonzero(good)) < 200:
        raise MastError("Fewer than 200 unflagged cadences in this sector.", 502)
    time = time[good]
    flux = flux[good]
    order = np.argsort(time)
    time = time[order]
    flux = flux[order]
    median = float(np.median(flux))
    if median == 0:
        raise MastError("PDCSAP median flux is zero.", 502)
    relative = flux / median
    start = float(time[0])
    return {
        "id": f"TIC-{tic}",
        "tic": tic,
        "name": f"TIC {tic}",
        "synthetic": False,
        "archive": "MAST",
        "observation_id": path.stem.split("-", 1)[-1] if path.stem.startswith(f"{tic}-") else path.stem,
        "ra_deg": round(ra, 6),
        "dec_deg": round(dec, 6),
        "sector": sector,
        "summary": (
            f"TESS SPOC PDCSAP light curve, sector {sector}. "
            "Quality-flagged cadences removed. One sector is not a confirmation."
        ),
        "btjd_start": round(start, 6),
        "time_days": [round(float(value - start), 6) for value in time],
        "flux": [round(float(value), 7) for value in relative],
        "n_raw": int(quality.size),
        "n_kept": int(time.size),
    }


def _invoke(request: dict) -> list[dict]:
    try:
        response = httpx.post(
            MAST_INVOKE,
            data={"request": json.dumps(request)},
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise MastError("MAST did not answer the observation query.") from exc
    if body.get("status") not in (None, "COMPLETE"):
        raise MastError(f"MAST returned status {body.get('status')}.")
    data = body.get("data")
    if not isinstance(data, list):
        raise MastError("MAST returned an unexpected payload.")
    return data


def _choose_observation(rows: list[dict]) -> dict:
    tess = [row for row in rows if str(row.get("obs_collection")) == "TESS"]
    if not tess:
        raise MastError("MAST has no TESS timeseries for that TIC.", 404)
    for exposure in EXPOSURE_PREFERENCE:
        matches = [row for row in tess if int(row.get("t_exptime") or 0) == exposure]
        if matches:
            return matches[0]
    return tess[0]


def _choose_light_curve(products: list[dict]) -> dict:
    curves = []
    for product in products:
        name = str(product.get("productFilename") or "")
        subgroup = str(product.get("productSubGroupDescription") or "")
        if subgroup == "LC" or name.endswith("_lc.fits"):
            curves.append(product)
    if not curves:
        raise MastError("The selected observation has no light-curve FITS file.", 404)
    curves.sort(key=lambda product: int(product.get("size") or 10**12))
    return curves[0]


def _download(uri: str, path: Path) -> None:
    temporary = path.with_suffix(path.suffix + f".{secrets.token_hex(8)}.part")
    try:
        with httpx.stream(
            "GET",
            MAST_DOWNLOAD + quote(uri, safe=""),
            headers={"User-Agent": USER_AGENT},
            timeout=120,
            follow_redirects=True,
        ) as response:
            response.raise_for_status()
            total = 0
            with temporary.open("wb") as handle:
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    if total > MAX_LIGHT_CURVE_BYTES:
                        raise MastError("MAST light curve exceeds the allowed size.", 413)
                    handle.write(chunk)
        temporary.replace(path)
    except httpx.HTTPError as exc:
        temporary.unlink(missing_ok=True)
        raise MastError("MAST did not finish the light-curve download.") from exc
    except MastError:
        temporary.unlink(missing_ok=True)
        raise
