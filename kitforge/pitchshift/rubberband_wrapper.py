"""Rubber Band R3 pitch shifting via pyrubberband."""
from __future__ import annotations

import numpy as np


def pitch_shift(audio: np.ndarray, sr: int, semitones: float) -> np.ndarray:
    """Shift audio by semitones using Rubber Band R3 engine. Returns float32."""
    import pyrubberband

    if semitones == 0.0:
        return audio.astype(np.float32)

    ratio = 2.0 ** (semitones / 12.0)
    shifted = pyrubberband.pitch_shift(audio, sr, n_steps=semitones)
    return shifted.astype(np.float32)
