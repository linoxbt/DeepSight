"""CPU transit search for short light curves.

The fitter is a box-least-squares grid. It reports a candidate period and a
white-noise signal-to-noise proxy. It does not confirm a planet.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

PIPELINE_NAME = "bls-numpy-v1"
PIPELINE_VERSION = "1"


@dataclass(frozen=True)
class TransitFit:
    period_days: float
    t0_days: float
    duration_days: float
    depth: float
    snr_proxy: float
    period_uncertainty_days: float
    bootstrap_uncertainty_days: float | None
    odd_even_delta: float
    secondary_depth: float
    n_in_transit: int
    periodogram_period: list[float]
    periodogram_power: list[float]


def synthetic_series(
    *,
    period_days: float,
    depth: float,
    duration_days: float,
    span_days: float = 27.4,
    cadence_minutes: float = 10.0,
    noise: float = 0.0007,
    t0_days: float = 1.15,
    seed: int = 1,
) -> tuple[np.ndarray, np.ndarray]:
    cadence_days = cadence_minutes / 1440.0
    count = int(span_days / cadence_days)
    time = np.arange(count, dtype=float) * cadence_days
    rng = np.random.default_rng(seed)
    flux = np.ones(count, dtype=float) + rng.normal(0.0, noise, count)
    phase = np.mod(time - t0_days, period_days)
    half = duration_days / 2.0
    in_transit = (phase <= half) | (phase >= period_days - half)
    flux[in_transit] -= depth
    return time, flux


def fit_transit(
    time: np.ndarray,
    flux: np.ndarray,
    *,
    period_min: float = 0.7,
    period_max: float = 12.0,
    n_periods: int = 700,
) -> TransitFit:
    if len(time) < 50 or len(time) != len(flux):
        raise ValueError("Light curve needs at least 50 paired samples")
    time = np.asarray(time, dtype=float)
    flux = np.asarray(flux, dtype=float)
    order = np.argsort(time)
    time = time[order]
    flux = flux[order]
    elapsed = time - time[0]
    baseline = float(np.median(flux))
    centered = flux - baseline

    periods = np.linspace(period_min, period_max, n_periods)
    fractions = (0.012, 0.02, 0.03, 0.045, 0.06, 0.09, 0.12)
    powers = np.empty(n_periods, dtype=float)
    best = None

    for index, period in enumerate(periods):
        winner = _best_box(elapsed, centered, float(period), fractions)
        powers[index] = winner[0]
        if best is None or winner[0] > best[0]:
            best = winner + (float(period),)

    assert best is not None
    period = best[-1]
    _snr, depth, t0, duration, count_in = _refine(elapsed, flux, period, baseline)
    sigma = float(np.std(centered[_out_of_transit(elapsed, period, t0, duration)]))
    snr = 0.0 if sigma == 0 else depth / sigma * float(np.sqrt(max(count_in, 1)))
    odd_even_delta, _odd, _even = _odd_even(elapsed, flux, period, t0, duration, baseline)
    secondary = _secondary_depth(elapsed, flux, period, t0, duration, baseline)
    step = float(periods[1] - periods[0]) if n_periods > 1 else period
    uncertainty = _bootstrap_period_uncertainty(elapsed, flux, period, t0, duration, depth, period_min, period_max, step, fractions)
    keep = np.linspace(0, n_periods - 1, min(160, n_periods)).astype(int)
    return TransitFit(
        period_days=period,
        t0_days=float(time[0] + t0),
        duration_days=duration,
        depth=depth,
        snr_proxy=float(snr),
        period_uncertainty_days=step,
        bootstrap_uncertainty_days=uncertainty,
        odd_even_delta=odd_even_delta,
        secondary_depth=secondary,
        n_in_transit=count_in,
        periodogram_period=[round(float(periods[i]), 5) for i in keep],
        periodogram_power=[round(float(powers[i]), 8) for i in keep],
    )


def _bootstrap_period_uncertainty(time, flux, period, t0, duration, depth, lower, upper, step, fractions):
    """Conditional white-noise bootstrap; it does not account for systematics or aliases."""
    if period <= lower + step or period >= upper - step or depth <= 0:
        return None
    phase = np.mod(time - t0, period)
    transit = (phase <= duration / 2) | (phase >= period - duration / 2)
    model = np.full(flux.size, float(np.median(flux)))
    model[transit] -= depth
    residuals = flux - model
    window = max(8 * step, period * 0.015)
    trials = np.linspace(max(lower, period - window), min(upper, period + window), 81)
    rng = np.random.default_rng(1408)
    recovered = []
    for _ in range(12):
        sample = model + rng.choice(residuals, size=residuals.size, replace=True)
        centered = sample - float(np.median(sample))
        scores = [_best_box(time, centered, float(candidate), fractions)[0] for candidate in trials]
        recovered.append(float(trials[int(np.argmax(scores))]))
    spread = float(np.std(recovered, ddof=1))
    return max(spread, float(trials[1] - trials[0]))


def fold(time: np.ndarray, flux: np.ndarray, period: float, t0: float, bins: int = 60) -> dict:
    # Shift by half a period so the transit sits in the middle of the plot.
    phase = np.mod((np.asarray(time, dtype=float) - t0) / period + 0.5, 1.0)
    flux = np.asarray(flux, dtype=float)
    edges = np.linspace(0.0, 1.0, bins + 1)
    centers = []
    values = []
    for start, stop in zip(edges[:-1], edges[1:]):
        selected = flux[(phase >= start) & (phase < stop)]
        if selected.size == 0:
            continue
        centers.append(round(float((start + stop) / 2.0), 5))
        values.append(round(float(np.median(selected)), 7))
    return {"phase": centers, "flux": values}


def quality_flags(fit: TransitFit, *, synthetic: bool, cross_match_result: str) -> list[dict]:
    flags = []
    if synthetic:
        flags.append(
            {
                "code": "synthetic_source",
                "severity": "warning",
                "message": "This series is a local calibration injection, not an archive observation.",
            }
        )
    if fit.n_in_transit < 8:
        flags.append(
            {
                "code": "sparse_in_transit",
                "severity": "warning",
                "message": "Fewer than 8 samples fall inside the best box.",
            }
        )
    if fit.odd_even_delta > 0.35:
        flags.append(
            {
                "code": "odd_even_mismatch",
                "severity": "warning",
                "message": "Odd and even transit depths disagree by more than 35 percent.",
            }
        )
    if fit.secondary_depth > max(0.4 * fit.depth, 0.001):
        flags.append(
            {
                "code": "possible_secondary",
                "severity": "warning",
                "message": "A dip near phase 0.5 survives the same duration cut.",
            }
        )
    if cross_match_result == "period_coincidence":
        flags.append(
            {
                "code": "period_coincidence",
                "severity": "warning",
                "message": "The period is close to a known object, but the target id does not match.",
            }
        )
    if fit.snr_proxy < 7:
        flags.append(
            {
                "code": "low_snr_proxy",
                "severity": "warning",
                "message": "The white-noise signal-to-noise proxy is below 7.",
            }
        )
    return flags


def _refine(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    baseline: float,
) -> tuple[float, float, float, float, int]:
    """Pick duration and epoch by white-noise signal-to-noise, not box length."""
    centered = flux - baseline
    best_rss = None
    best = (0.0, 0.0, 0.0, period * 0.04, 0)
    for fraction in np.linspace(0.012, 0.08, 28):
        duration = float(fraction * period)
        half = duration / 2.0
        for t0 in np.linspace(0.0, period, 56, endpoint=False):
            phase = np.mod(time - t0, period)
            mask = (phase <= half) | (phase >= period - half)
            count = int(np.count_nonzero(mask))
            outside = int(centered.size - count)
            if count < 5 or outside < 5:
                continue
            mean_in = float(np.mean(centered[mask]))
            mean_out = float(np.mean(centered[~mask]))
            depth = -mean_in
            if depth <= 0:
                continue
            residual_in = centered[mask] - mean_in
            residual_out = centered[~mask] - mean_out
            rss = float(np.dot(residual_in, residual_in) + np.dot(residual_out, residual_out))
            if best_rss is None or rss < best_rss:
                best_rss = rss
                best = (0.0, float(depth), float(t0), duration, count)
    return best


def _best_box(
    time: np.ndarray,
    centered: np.ndarray,
    period: float,
    fractions: tuple[float, ...],
) -> tuple[float, float, float, float, int]:
    phase = np.mod(time, period) / period
    order = np.argsort(phase)
    samples = centered[order]
    phases = phase[order]
    cumulative = np.concatenate(([0.0], np.cumsum(samples)))
    total = samples.size
    best_power = -1.0
    best = (0.0, 0.0, 0.0, 0.0, 0)
    starts = np.linspace(0.0, 1.0, 48, endpoint=False)
    for fraction in fractions:
        duration = fraction * period
        for start in starts:
            stop = float(start + fraction)
            if stop <= 1.0:
                left = int(np.searchsorted(phases, start, side="left"))
                right = int(np.searchsorted(phases, stop, side="left"))
                count = right - left
                if count < 3:
                    continue
                box_sum = float(cumulative[right] - cumulative[left])
                center_phase = float(start + fraction / 2.0)
            else:
                right = int(np.searchsorted(phases, stop - 1.0, side="left"))
                left = int(np.searchsorted(phases, start, side="left"))
                count = right + (total - left)
                if count < 3:
                    continue
                box_sum = float(cumulative[right] + (cumulative[total] - cumulative[left]))
                center_phase = float((start + fraction / 2.0) % 1.0)
            mean_in = box_sum / count
            # A transit is a negative residual relative to the series median.
            depth = -mean_in
            if depth <= 0:
                continue
            power = depth * depth * count * (total - count) / total
            if power > best_power:
                best_power = power
                best = (power, float(depth), center_phase * period, float(duration), count)
    return best


def _out_of_transit(time: np.ndarray, period: float, t0: float, duration: float) -> np.ndarray:
    phase = np.mod(time - t0, period)
    half = duration / 2.0
    return ~((phase <= half) | (phase >= period - half))


def _odd_even(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float,
    baseline: float,
) -> tuple[float, float, float]:
    phase = np.mod(time - t0, period)
    half = duration / 2.0
    in_transit = (phase <= half) | (phase >= period - half)
    epoch = np.round((time - t0) / period).astype(int)
    odd = in_transit & (np.mod(epoch, 2) != 0)
    even = in_transit & (np.mod(epoch, 2) == 0)
    if not np.any(odd) or not np.any(even):
        return 1.0, 0.0, 0.0
    depth_odd = baseline - float(np.median(flux[odd]))
    depth_even = baseline - float(np.median(flux[even]))
    scale = max(depth_odd, depth_even, 1e-8)
    return abs(depth_odd - depth_even) / scale, depth_odd, depth_even


def _secondary_depth(
    time: np.ndarray,
    flux: np.ndarray,
    period: float,
    t0: float,
    duration: float,
    baseline: float,
) -> float:
    half = duration / 2.0
    primary = np.mod(time - t0, period)
    in_primary = (primary <= half) | (primary >= period - half)
    secondary = np.mod(time - (t0 + period / 2.0), period)
    in_secondary = ((secondary <= half) | (secondary >= period - half)) & ~in_primary
    if not np.any(in_secondary):
        return 0.0
    return max(0.0, baseline - float(np.median(flux[in_secondary])))
