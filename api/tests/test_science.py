from api.catalogue import cross_match
from api.science import fit_transit, synthetic_series


def test_recovers_injected_period():
    period = 2.507
    time, flux = synthetic_series(
        period_days=period,
        depth=0.0084,
        duration_days=0.11,
        seed=261136679,
    )
    fit = fit_transit(time, flux)
    assert abs(fit.period_days - period) / period < 0.01
    assert abs(fit.depth - 0.0084) / 0.0084 < 0.25
    assert abs(fit.duration_days - 0.11) < 0.03
    assert fit.snr_proxy > 7
    assert fit.odd_even_delta < 0.35


def test_period_coincidence_is_not_an_identification():
    match = cross_match("DS-SYN-002", 6.2679)
    assert match["result"] == "period_coincidence"
    assert "not an identification" in match["note"]


def test_unknown_target_has_no_catalogue_hit():
    match = cross_match("DS-SYN-001", 2.507)
    assert match["result"] == "no_exact_match"


def test_gapped_series_agrees_with_astropy_reference():
    import numpy as np
    from astropy.timeseries import BoxLeastSquares
    time, flux = synthetic_series(period_days=2.507, depth=0.0084, duration_days=0.11, seed=42)
    keep = ~((time > 8) & (time < 10))
    time, flux = time[keep], flux[keep]
    fit = fit_transit(time, flux)
    periods = np.linspace(2.3, 2.7, 2000)
    reference = BoxLeastSquares(time, flux).power(periods, [0.08, 0.11, 0.14])
    period = float(reference.period[np.argmax(reference.power)])
    assert abs(fit.period_days - period) <= fit.period_uncertainty_days
    assert abs(fit.depth - 0.0084) < 0.002
