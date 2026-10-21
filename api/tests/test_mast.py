import random

import numpy as np
from astropy.io import fits
from astropy.table import Table
from fastapi.testclient import TestClient

from api.main import app
from api.mast import MastError, normalize_tic, read_spoc_light_curve

client = TestClient(app)
client.__enter__()


def test_tic_must_be_numeric():
    try:
        normalize_tic("not-a-tic")
    except MastError as exc:
        assert exc.status_code == 422
    else:
        raise AssertionError("expected MastError")
    assert normalize_tic("TIC 259377017") == "259377017"


def test_spoc_reader_drops_flagged_and_blank_cadences(tmp_path):
    count = 320
    time = np.linspace(2100, 2126, count)
    flux = np.full(count, 1200.0)
    quality = np.zeros(count, dtype=int)
    quality[:8] = 1
    flux[20:24] = np.nan
    table = Table({"TIME": time, "PDCSAP_FLUX": flux, "QUALITY": quality})
    path = tmp_path / "sector.fits"
    primary = fits.PrimaryHDU()
    primary.header["SECTOR"] = 30
    primary.header["TICID"] = 259377017
    primary.header["RA_OBJ"] = 68.4
    primary.header["DEC_OBJ"] = -51.9
    fits.HDUList([primary, fits.BinTableHDU(table)]).writeto(path)

    curve = read_spoc_light_curve(path)
    assert curve["tic"] == "259377017"
    assert curve["sector"] == 30
    assert curve["archive"] == "MAST"
    assert curve["n_kept"] == count - 8 - 4
    assert curve["time_days"][0] == 0
    assert abs(curve["flux"][0] - 1) < 1e-6


def test_import_caches_a_mast_curve(monkeypatch, tmp_path):
    calls = {"n": 0}
    tic_id = str(random.randint(800_000_000, 899_999_999))
    raw_path = tmp_path / "sector_lc.fits"
    fits.HDUList([fits.PrimaryHDU()]).writeto(raw_path)

    def fake(tic, cache_dir=None):
        calls["n"] += 1
        time = list(np.linspace(0, 27, 400))
        return {
            "id": f"TIC-{tic}",
            "tic": tic,
            "name": "TIC 259377017",
            "synthetic": False,
            "archive": "MAST",
            "observation_id": "s0030-lc",
            "ra_deg": 68.4,
            "dec_deg": -51.9,
            "sector": 30,
            "summary": "TESS sector 30",
            "btjd_start": 2115.0,
            "time_days": time,
            "flux": [1.0] * len(time),
            "n_raw": 420,
            "n_kept": 400,
            "exposure_seconds": 120,
            "product_filename": "sector_lc.fits",
            "data_uri": "mast:TESS/product/sector_lc.fits",
            "raw_path": str(raw_path),
        }

    monkeypatch.setattr("api.main.fetch_tess_light_curve", fake)
    created = client.post("/v1/datasets/import", json={"tic": tic_id})
    assert created.status_code == 200
    body = created.json()
    assert body["cached"] is False
    assert body["target"]["archive"] == "MAST"
    assert "time_days" not in body["target"]
    assert len(body["target"]["raw_sha256"]) == 64
    assert client.get(body["target"]["raw_uri"]).status_code == 200

    again = client.post("/v1/datasets/import", json={"tic": tic_id})
    assert again.status_code == 200
    assert again.json()["cached"] is True
    assert calls["n"] == 1

    listed = client.get("/v1/targets").json()["targets"]
    assert any(item["id"] == f"TIC-{tic_id}" and item["synthetic"] is False for item in listed)

    rejected = client.post("/v1/datasets/import", json={"tic": "star"})
    assert rejected.status_code == 422
