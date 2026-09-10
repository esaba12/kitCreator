"""Autocorrelation loop-point finder for sustained pitched samples."""
from __future__ import annotations

import numpy as np


# Skip looping if steady-state RMS < this fraction of peak (pure decay)
_MIN_SUSTAIN_FRAC = 0.15

# Search window for aligning to a zero crossing
_ZC_SEARCH = 512

# Autocorrelation peak threshold; below this means signal isn't periodic
_AC_THRESHOLD = 0.3


def find_loop(audio: np.ndarray, sr: int) -> tuple[int, int] | None:
    """
    Return (loop_start, loop_end) sample offsets for sustained signals.

    Returns None when the signal decays too quickly for a clean loop
    (guitar, plucked bass, drum tail) or when no clear period is found.
    """
    n = len(audio)
    if n < int(0.3 * sr):           # need at least 300 ms
        return None

    peak = float(np.abs(audio).max())
    if peak == 0.0:
        return None

    # Analyse the middle half for periodicity (skip attack + tail noise)
    analysis_lo = n // 4
    analysis_hi = 3 * n // 4
    region = audio[analysis_lo:analysis_hi]

    # Reject signals that decay too quickly to loop cleanly
    region_rms = float(np.sqrt(np.mean(region ** 2)))
    if region_rms / peak < _MIN_SUSTAIN_FRAC:
        return None

    period = _estimate_period(region, sr)
    if period is None:
        return None

    # Loop start: beginning of analysis region, snapped to nearest zero crossing
    loop_start = _nearest_zc(audio, analysis_lo)

    # Fit as many full periods as possible, staying inside the sample
    max_end = min(loop_start + int(2.0 * sr), 3 * n // 4)
    n_periods = max(1, (max_end - loop_start) // period)
    if loop_start + n_periods * period >= n:
        n_periods = max(1, n_periods - 1)

    loop_end = _nearest_zc(audio, loop_start + n_periods * period)

    if loop_end <= loop_start or loop_end >= n - 1:
        return None

    return (loop_start, loop_end)


def _estimate_period(region: np.ndarray, sr: int) -> int | None:
    """Return dominant period in samples via normalized autocorrelation."""
    min_lag = max(1, int(sr / 2000))  # 2000 Hz ceiling
    max_lag = int(sr / 50)            # 50 Hz floor

    if len(region) < 2 * max_lag:
        return None

    ac = np.correlate(region, region, mode="full")
    ac = ac[len(ac) // 2:]               # positive lags only
    ac = ac / (ac[0] + 1e-10)            # normalize

    candidates = ac[min_lag : max_lag + 1]
    if len(candidates) == 0:
        return None

    peak_idx = int(np.argmax(candidates))
    if candidates[peak_idx] < _AC_THRESHOLD:
        return None                       # weak / aperiodic signal

    return peak_idx + min_lag


def _nearest_zc(audio: np.ndarray, center: int) -> int:
    """Return sample index of the zero crossing nearest to center."""
    lo = max(0, center - _ZC_SEARCH)
    hi = min(len(audio) - 1, center + _ZC_SEARCH)
    region = audio[lo : hi + 1]
    signs = np.sign(region)
    crossings = np.where(np.diff(signs) != 0)[0]
    if len(crossings) == 0:
        return center
    nearest = int(crossings[np.argmin(np.abs(crossings - (center - lo)))])
    return lo + nearest
