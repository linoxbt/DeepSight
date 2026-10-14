import os

from api.archives import query_horizons, resolve_cross_match


def test_cross_match_uses_live_tap_rows(monkeypatch):
    os.environ["DEEPSIGHT_LIVE_TAP"] = "1"
    try:
        def fake_fetch(**_kwargs):
            return [
                {
                    "name": "TOI-270 c",
                    "hostname": "TOI-270",
                    "period_days": 5.66051,
                    "ra_deg": 68.416,
                    "dec_deg": -51.957,
                    "tic_id": "TIC 259377017",
                    "host_tic": "259377017",
                }
            ]

        monkeypatch.setattr("api.archives.fetch_planets", fake_fetch)
        match = resolve_cross_match("TIC-259377017", 5.662947, tic="259377017", ra=68.41, dec=-51.95)
        assert match["live_query"] is True
        assert match["result"] == "known_object"
        assert "TAP" in match["note"]
    finally:
        os.environ["DEEPSIGHT_LIVE_TAP"] = "0"


def test_cross_match_falls_back_when_tap_fails(monkeypatch):
    os.environ["DEEPSIGHT_LIVE_TAP"] = "1"
    try:
        def explode(**_kwargs):
            from api.archives import ArchiveError

            raise ArchiveError("down")

        monkeypatch.setattr("api.archives.fetch_planets", explode)
        match = resolve_cross_match("DS-SYN-001", 2.51)
        assert match["live_query"] is False
        assert "local extract" in match["note"]
    finally:
        os.environ["DEEPSIGHT_LIVE_TAP"] = "0"


def test_horizons_reports_a_miss():
    result = query_horizons.__wrapped__ if hasattr(query_horizons, "__wrapped__") else None
    assert result is None
    from api.archives import _ephemeris_lines

    text = "No matches found\nMatching small-bodies:\nNo matches found"
    assert _ephemeris_lines(text) == []
    sample = "header\n$$SOE\n 2026-Oct-14 00:00  12.0\n$$EOE\n"
    assert _ephemeris_lines(sample) == ["2026-Oct-14 00:00  12.0"]


def test_tap_route_rejects_a_blank_query():
    from fastapi.testclient import TestClient

    from api.main import app

    client = TestClient(app)
    response = client.post("/v1/archives/tap", json={})
    assert response.status_code == 422
