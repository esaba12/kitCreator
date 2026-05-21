"""ADSR envelope estimation from normalized audio clips."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class ADSRParams:
    attack: float    # seconds
    decay: float     # seconds
    sustain: float   # 0–100 (SFZ ampeg_sustain %; 100 = full level)
    release: float   # seconds


_HOP_MS = 5.0         # RMS analysis hop in milliseconds
_RELEASE_DB = -40.0   # define "release end" at this dB below peak


def estimate_adsr(audio: np.ndarray, sr: int) -> ADSRParams:
    """
    Estimate ADSR from the RMS envelope of a normalized mono clip.

    Works for both drum one-shots (short attack, long free-decay) and
    sustained pitched samples (distinct sustain plateau).
    """
    hop = max(1, int(_HOP_MS / 1000.0 * sr))
    n_hops = max(1, len(audio) // hop)

    rms = np.array([
        np.sqrt(np.mean(audio[i * hop : (i + 1) * hop] ** 2))
        for i in range(n_hops)
    ])

    if rms.max() == 0.0:
        return ADSRParams(0.01, 0.1, 100.0, 0.1)

    peak_idx = int(np.argmax(rms))
    peak_rms = float(rms[peak_idx])
    hop_s = _HOP_MS / 1000.0

    # ── Attack ───────────────────────────────────────────────────────────────────
    attack_s = max(0.001, peak_idx * hop_s)

    # ── Sustain level: median RMS in the central 60 % of the clip ────────────────
    n = len(rms)
    mid_lo = max(peak_idx + 1, n // 5)
    mid_hi = max(mid_lo + 1, 4 * n // 5)
    sustain_rms = float(np.median(rms[mid_lo:mid_hi])) if mid_hi > mid_lo else peak_rms * 0.5
    sustain_pct = float(np.clip(100.0 * sustain_rms / peak_rms, 0.0, 100.0))

    # ── Decay: time from peak to within 5 % above sustain level ─────────────────
    decay_target = sustain_rms * 1.05
    decay_idx = peak_idx
    for i in range(peak_idx, n):
        if rms[i] <= decay_target:
            decay_idx = i
            break
    decay_s = max(0.001, (decay_idx - peak_idx) * hop_s)

    # ── Release: time from decay end to _RELEASE_DB below peak ──────────────────
    release_threshold = peak_rms * (10 ** (_RELEASE_DB / 20.0))
    release_end_idx = n - 1
    for i in range(n - 1, decay_idx, -1):
        if rms[i] >= release_threshold:
            release_end_idx = i
            break
    release_s = max(0.05, (release_end_idx - decay_idx) * hop_s)

    return ADSRParams(
        attack=round(attack_s, 4),
        decay=round(decay_s, 4),
        sustain=round(sustain_pct, 2),
        release=round(release_s, 4),
    )
