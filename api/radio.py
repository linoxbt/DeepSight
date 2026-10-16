"""Breakthrough Listen catalog search and one sampled calibration spectrum.

Catalog rows point at multi-gigabyte baseband files. This module lists them
and does not download them. The only product it fetches is the public Voyager 1
tutorial HDF5, about 50 MB, used as a calibration screen.
"""

from __future__ import annotations

import hashlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx
import numpy as np

from api.archives import ArchiveError
from api.manifest import canonicalize, sha256_text

CATALOG_URL = "https://breakthroughinitiatives.org/opendatasearch"
TUTORIAL_URL = "http://blpd0.ssl.berkeley.edu/Voyager_data/Voyager1.single_coarse.fine_res.h5"
TUTORIAL_NAME = "Voyager1.single_coarse.fine_res.h5"
TUTORIAL_SHA256 = "c9a9a54f4140e3754ffb2455fae4eeb2eb70c8207123116ee953e4fce15c36ac"
MAX_TUTORIAL_BYTES = 100 * 1024 * 1024
USER_AGENT = "DeepSight/0.1"
ARCHIVE_NAME = "Breakthrough Listen"


class _CatalogParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None
        self._href = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: (value or "") for key, value in attrs}
        if tag == "tr" and "grey" in values.get("class", ""):
            self._row = []
        elif tag == "td" and self._row is not None:
            self._cell = []
            self._href = ""
        elif tag == "a" and self._cell is not None and values.get("href"):
            self._href = values["href"]

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None and self._row is not None:
            text = " ".join("".join(self._cell).split())
            self._row.append(self._href or text)
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if len(self._row) >= 10:
                self.rows.append(self._row)
            self._row = None


def search_catalog(target: str) -> dict[str, Any]:
    cleaned = target.strip()
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_+-.")
    if not cleaned or len(cleaned) > 40 or any(character not in allowed for character in cleaned):
        raise ArchiveError("Enter a Breakthrough Listen target token, for example VOYAGER1.", 422)
    try:
        with httpx.Client(timeout=40, follow_redirects=True) as client:
            response = client.get(
                CATALOG_URL,
                params={
                    "project": "all",
                    "target": cleaned,
                    "file_type": "all",
                    "search": "Search",
                    "perPage": "20",
                },
                headers={"User-Agent": USER_AGENT},
            )
            response.raise_for_status()
            page = response.text
    except httpx.HTTPError as exc:
        raise ArchiveError("The Breakthrough Listen catalog did not answer.") from exc
    parser = _CatalogParser()
    parser.feed(page)
    observations = []
    for row in parser.rows[:20]:
        try:
            size_bytes = int(float(row[8]))
        except ValueError:
            size_bytes = 0
        observations.append(
            {
                "utc": row[0],
                "mjd": row[1],
                "project": row[2],
                "target": row[3],
                "ra_deg": _float_or_none(row[4]),
                "dec_deg": _float_or_none(row[5]),
                "center_freq_mhz": _float_or_none(row[6]),
                "file_type": row[7],
                "size_bytes": size_bytes,
                "md5": row[9],
                "download_url": row[10] if len(row) > 10 else "",
                "downloaded": False,
            }
        )
    return {
        "live_query": True,
        "archive": ARCHIVE_NAME,
        "target": cleaned,
        "observations": observations,
        "note": (
            "These are catalog rows. DeepSight does not download the baseband or HDF5 products listed here. "
            "Multi-gigabyte files stay at the archive."
        ),
    }


def analyze_tutorial(cache_dir: Path) -> dict[str, Any]:
    path, digest = ensure_tutorial(cache_dir)
    loaded = read_h5(path)
    screen = screen_spectrum(loaded["frequency_mhz"], loaded["power"], loaded.get("peak_time_fraction"))
    result = public_radio_result(
        observation_id=path.stem,
        source_name=loaded["source_name"],
        frequency_range=loaded["frequency_range"],
        time_range=loaded["time_range"],
        screen=screen,
        artifact_sha256=digest,
        data_uri=TUTORIAL_URL,
        product_filename=path.name,
    )

    from api.evidence import put_json
    finite = np.isfinite(loaded["frequency_mhz"]) & np.isfinite(loaded["power"])
    result["spectrum_sha256"] = put_json({
        "frequency_mhz": loaded["frequency_mhz"][finite].tolist(),
        "power": loaded["power"][finite].tolist(),
        "peak_time_fraction": loaded["peak_time_fraction"],
    })
    return result


def ensure_tutorial(cache_dir: Path) -> tuple[Path, str]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / TUTORIAL_NAME
    if path.exists():
        if path.stat().st_size <= MAX_TUTORIAL_BYTES and _sha256_file(path) == TUTORIAL_SHA256:
            return path, TUTORIAL_SHA256
        path.unlink()
    temporary = path.with_suffix(".part")
    try:
        with httpx.Client(timeout=180, follow_redirects=True) as client:
            with client.stream("GET", TUTORIAL_URL, headers={"User-Agent": USER_AGENT}) as response:
                response.raise_for_status()
                total = 0
                with temporary.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        total += len(chunk)
                        if total > MAX_TUTORIAL_BYTES:
                            raise ArchiveError("The Voyager product exceeds the allowed size.", 413)
                        handle.write(chunk)
        if _sha256_file(temporary) != TUTORIAL_SHA256:
            raise ArchiveError("The Voyager product failed its pinned checksum.")
    except httpx.HTTPError as exc:
        temporary.unlink(missing_ok=True)
        raise ArchiveError("The Voyager calibration product did not finish downloading.") from exc
    except ArchiveError:
        temporary.unlink(missing_ok=True)
        raise
    temporary.replace(path)
    return path, TUTORIAL_SHA256


def read_h5(path: Path) -> dict[str, Any]:
    import h5py
    import hdf5plugin  # registers the bitshuffle filter used by Breakthrough Listen files

    del hdf5plugin

    with h5py.File(path, "r") as handle:
        if "data" not in handle:
            raise ArchiveError("The HDF5 product has no data dataset.")
        dataset = handle["data"]
        array = np.asarray(dataset[()], dtype=float)
        header = {}
        for source in (handle.attrs, dataset.attrs):
            for key in source:
                header[key] = _attr_text(source[key])
    nchans = _header_float(header, "nchans")
    if nchans and array.shape[-1] != int(nchans) and array.shape[0] == int(nchans):
        array = np.moveaxis(array, 0, -1)
    spectrum = np.nanmean(array, axis=0)
    while spectrum.ndim > 1:
        spectrum = np.nanmean(spectrum, axis=0)
    finite = np.isfinite(spectrum)
    if int(finite.sum()) < 32:
        raise ArchiveError("The spectrum does not contain enough finite channels.")
    fch1 = _header_float(header, "fch1")
    foff = _header_float(header, "foff")
    if fch1 is None or foff is None:
        frequency = np.arange(spectrum.size, dtype=float)
        frequency_range = "channel index; the file header has no fch1/foff"
    else:
        frequency = fch1 + np.arange(spectrum.size, dtype=float) * foff
        low = float(np.min(frequency))
        high = float(np.max(frequency))
        frequency_range = f"{low:.6f}-{high:.6f} MHz"
    tstart = _header_float(header, "tstart")
    source = header.get("source_name") or path.stem
    time_range = f"MJD {tstart:.5f}" if tstart is not None else "MJD unavailable in the file header"
    peak_time_fraction = _peak_time_fraction(array, spectrum)
    return {
        "frequency_mhz": frequency,
        "power": spectrum,
        "source_name": str(source).strip() or path.stem,
        "frequency_range": frequency_range,
        "time_range": time_range,
        "peak_time_fraction": peak_time_fraction,
    }


def screen_spectrum(
    frequency_mhz: np.ndarray,
    power: np.ndarray,
    peak_time_fraction: float | None = None,
) -> dict[str, Any]:
    frequency = np.asarray(frequency_mhz, dtype=float)
    values = np.asarray(power, dtype=float)
    finite = np.isfinite(frequency) & np.isfinite(values)
    frequency = frequency[finite]
    values = values[finite]
    if values.size < 32:
        raise ArchiveError("The spectrum needs at least 32 finite channels.", 422)
    residual = values - _broad_baseline(values)
    median = float(np.median(residual))
    mad = float(np.median(np.abs(residual - median)))
    scale = mad * 1.4826 if mad > 0 else float(np.std(residual) or 1.0)
    score = (residual - median) / scale
    hit_indexes = np.flatnonzero(score > 8)
    spans = _group(hit_indexes)
    spans.sort(key=lambda item: float(np.max(score[item[0] : item[1] + 1])), reverse=True)
    hits = []
    for start, stop in spans[:8]:
        segment = score[start : stop + 1]
        peak = start + int(np.argmax(segment))
        hits.append(
            {
                "channel_start": int(start),
                "channel_stop": int(stop),
                "frequency_mhz": round(float(frequency[peak]), 6),
                "mad_score": round(float(score[peak]), 3),
            }
        )
    edge = max(1, values.size // 50)
    edge_hits = int(np.sum((hit_indexes < edge) | (hit_indexes >= values.size - edge))) if hit_indexes.size else 0
    plot = _max_bins(frequency, residual, median, 400)
    return {
        "snr_proxy": round(float(np.max(score)), 3),
        "n_hits": int(hit_indexes.size),
        "n_spans": len(spans),
        "hits": hits,
        "edge_hit_fraction": round(edge_hits / hit_indexes.size, 4) if hit_indexes.size else 0.0,
        "peak_time_fraction": None if peak_time_fraction is None else round(float(peak_time_fraction), 4),
        "rfi_tests": ["narrowband_mad", "band_edge", "time_persistence"],
        "plot": plot,
        "median": median,
    }


def public_radio_result(
    *,
    observation_id: str,
    source_name: str,
    frequency_range: str,
    time_range: str,
    screen: dict[str, Any],
    artifact_sha256: str,
    data_uri: str,
    product_filename: str,
) -> dict[str, Any]:
    voyager = "voyager" in source_name.lower() or "voyager" in observation_id.lower()
    science = "known_object" if voyager else "inconclusive"
    limitations = [
        "A narrowband excess is not a technosignature and is not an extraterrestrial detection.",
        "No off-target pointing was compared, so this package cannot satisfy the signal policy on its own.",
        "This is one public calibration product, not a survey.",
    ]
    if voyager:
        limitations.append("The file identifies Voyager 1, a human spacecraft used as a calibration target.")
        if screen["hits"]:
            limitations.append(
                f"The strongest narrow channel is at {screen['hits'][0]['frequency_mhz']} MHz. "
                "In this tutorial file that is the Voyager 1 carrier, not a new signal."
            )
    return {
        "target_name": source_name,
        "synthetic": False,
        "archive": ARCHIVE_NAME,
        "observation_id": observation_id,
        "scientific_status": science,
        "frequency_range": frequency_range,
        "time_range": time_range,
        "snr_method": "median-absolute-deviation of the time-averaged spectrum",
        "calibration": "Archive HDF5 as released. DeepSight did not recalibrate the bandpass.",
        "off_target_comparison": "unavailable",
        "rfi_tests": screen["rfi_tests"],
        "metrics": {
            "snr_proxy": screen["snr_proxy"],
            "n_hits": screen["n_hits"],
            "n_spans": screen["n_spans"],
            "edge_hit_fraction": screen["edge_hit_fraction"],
            "peak_time_fraction": screen["peak_time_fraction"],
        },
        "hits": screen["hits"],
        "plot": screen["plot"],
        "limitations": limitations,
        "artifact_sha256": artifact_sha256,
        "data_uri": data_uri,
        "product_filename": product_filename,
        "note": "The screen flags narrow channels. It does not verify an alien signal.",
    }


def build_radio_manifest(result: dict[str, Any], *, analysis_id: str, git_commit: str, claimant_address: str, researcher_address: str) -> dict[str, Any]:
    document = {
        "schema_version": "1.1",
        "claimant_address": claimant_address,
        "researcher_address": researcher_address,
        "claim_type": "radio_signal_integrity",
        "policy_version": "signal-v1",
        "target": {"id": result["target_name"]},
        "archive": {"name": ARCHIVE_NAME, "observation_ids": [result["observation_id"]], "raw_source_uri": result["data_uri"], "raw_source_sha256": result["artifact_sha256"]},
        "signal": {
            "observation_id": result["observation_id"],
            "frequency_range": result["frequency_range"],
            "time_range": result["time_range"],
            "snr_method": result["snr_method"],
            "calibration": result["calibration"],
        },
        "analysis": {
            "git_commit": git_commit,
            "container_digest": "",
            "environment_sha256": result.get("environment_sha256", ""),
            "pipeline": "radio-mad-v1",
            "pipeline_version": "1",
        },
        "metrics": [
            {"name": "snr_proxy", "value": result["metrics"]["snr_proxy"], "unit": "mad", "uncertainty": None}
        ],
        "artifacts": [
            {
                "sha256": result.get("report_sha256") or result["artifact_sha256"],
                "uri": f"/v1/artifacts/{result['report_sha256']}" if result.get("report_sha256") else result["data_uri"],
                "kind": "screening_report",
            }
        ],
        "rfi_tests": result["rfi_tests"],
        "off_target_comparison": result["off_target_comparison"],
        "limitations": result["limitations"],
        "scientific_status": result["scientific_status"],
    }
    if result.get("spectrum_sha256"):
        document["artifacts"].append({"sha256": result["spectrum_sha256"], "uri": f"/v1/artifacts/{result['spectrum_sha256']}", "kind": "spectrum"})
    text = canonicalize(document)
    return {"document": document, "text": text, "sha256": sha256_text(text), "analysis_id": analysis_id}


def _broad_baseline(values: np.ndarray) -> np.ndarray:
    block = 4096 if values.size >= 4096 else max(3, values.size // 8)
    count = values.size // block
    if count < 3:
        return np.full(values.size, float(np.median(values)))
    coarse = np.median(values[: count * block].reshape(count, block), axis=1)
    centers = (np.arange(count) + 0.5) * block
    return np.interp(np.arange(values.size), centers, coarse)


def _group(indexes: np.ndarray) -> list[tuple[int, int]]:
    if indexes.size == 0:
        return []
    spans = []
    start = previous = int(indexes[0])
    for value in indexes[1:]:
        current = int(value)
        if current == previous + 1:
            previous = current
            continue
        spans.append((start, previous))
        start = previous = current
    spans.append((start, previous))
    return spans


def _max_bins(frequency: np.ndarray, values: np.ndarray, median: float, bins: int) -> dict[str, list[float]]:
    if values.size <= bins:
        chosen = np.arange(values.size)
    else:
        edges = np.linspace(0, values.size, bins + 1).astype(int)
        chosen = []
        for start, stop in zip(edges[:-1], edges[1:]):
            if stop <= start:
                continue
            chosen.append(start + int(np.argmax(values[start:stop])))
        chosen = np.asarray(chosen, dtype=int)
    scale = float(np.max(np.abs(values - median)) or 1.0)
    return {
        "frequency_mhz": [round(float(frequency[index]), 6) for index in chosen],
        "relative_power": [round(float((values[index] - median) / scale), 5) for index in chosen],
    }


def _peak_time_fraction(array: np.ndarray, spectrum: np.ndarray) -> float | None:
    if array.ndim < 2:
        return None
    flat = np.nanmean(array, axis=tuple(range(1, array.ndim - 1))) if array.ndim > 2 else array
    if flat.ndim != 2 or flat.shape[0] < 2:
        return None
    residual = spectrum - _broad_baseline(spectrum)
    peak = int(np.nanargmax(residual))
    column = flat[:, peak]
    column = column[np.isfinite(column)]
    if column.size < 2:
        return None
    reference = float(np.nanmedian(spectrum))
    return float(np.mean(column > reference))


def _header_float(header: dict[str, str], key: str) -> float | None:
    value = header.get(key)
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except ValueError:
        return None


def _attr_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    if isinstance(value, np.ndarray):
        if value.shape == ():
            return _attr_text(value.item())
        return " ".join(_attr_text(item) for item in value)
    return str(value)


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except ValueError:
        return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
