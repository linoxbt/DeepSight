import numpy as np

from api.policy import RESULT_REVIEW, evaluate
from api.radio import _CatalogParser, build_radio_manifest, public_radio_result, screen_spectrum


def test_screen_finds_a_narrow_spike_and_not_a_technosignature():
    frequency = np.linspace(8400, 8440, 400)
    power = np.ones(400)
    power[220] = 40
    screen = screen_spectrum(frequency, power, peak_time_fraction=0.9)
    assert screen["n_hits"] >= 1
    assert screen["hits"][0]["frequency_mhz"] == round(float(frequency[220]), 6)
    result = public_radio_result(
        observation_id="Voyager1.single_coarse.fine_res",
        source_name="Voyager1",
        frequency_range="8400-8440 MHz",
        time_range="MJD 57396.8",
        screen=screen,
        artifact_sha256="ab" * 32,
        data_uri="http://example.test/voyager.h5",
        product_filename="Voyager1.single_coarse.fine_res.h5",
    )
    assert result["scientific_status"] == "known_object"
    assert result["off_target_comparison"] == "unavailable"
    built = build_radio_manifest(result, analysis_id="rad_test", git_commit="abc")
    outcome, rationale = evaluate(built["text"], "radio_signal_integrity", "signal-v1")
    assert outcome == RESULT_REVIEW
    assert "off-target" in rationale
    assert "extraterrestrial" not in rationale.lower()


def test_catalog_parser_reads_a_row_without_downloading_it():
    page = """
    <tr class="grey">
      <td>2016-01-09 20:23:11</td>
      <td>57396.8494</td>
      <td>GBT</td>
      <td>VOYAGER1</td>
      <td>258.0674</td>
      <td>11.9629</td>
      <td>9281.25</td>
      <td>baseband data</td>
      <td>4232871936</td>
      <td>b3806523200507bbf53dbaf251f177e5</td>
      <td><a href="http://example.test/file.raw">download</a></td>
    </tr>
    """
    parser = _CatalogParser()
    parser.feed(page)
    assert parser.rows[0][3] == "VOYAGER1"
    assert parser.rows[0][10] == "http://example.test/file.raw"
