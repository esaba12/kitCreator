"""Monophonic f0 tracking via torchcrepe (replaces the unmaintained crepe PyPI package)."""
from __future__ import annotations

import numpy as np
import torch


def track_f0(
    audio: np.ndarray,
    sample_rate: int,
    hop_length: int = 512,
    fmin: float = 32.7,
    fmax: float = 2093.0,
    model: str = "full",
    batch_size: int = 2048,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (times, f0, confidence) arrays for a monophonic audio signal."""
    import torchcrepe

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    audio_tensor = torch.from_numpy(audio).float().unsqueeze(0)

    times, f0, confidence, _ = torchcrepe.predict(
        audio_tensor,
        sample_rate,
        hop_length=hop_length,
        fmin=fmin,
        fmax=fmax,
        model=model,
        batch_size=batch_size,
        device=device,
        return_periodicity=True,
    )
    return times.numpy(), f0.numpy(), confidence.numpy()
