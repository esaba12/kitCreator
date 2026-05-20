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
    batch_size: int = 512,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return (times_s, f0_hz, periodicity) arrays for a monophonic audio signal."""
    import torchcrepe

    # torchcrepe MPS support is inconsistent; CPU is safe and fast enough for bass stems
    device = "cpu"
    audio_tensor = torch.from_numpy(audio).float().unsqueeze(0)

    # predict returns (frequencies, periodicity) with return_periodicity=True
    f0_tensor, periodicity_tensor = torchcrepe.predict(
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

    n_frames = f0_tensor.shape[-1]
    times = np.arange(n_frames) * hop_length / sample_rate
    f0 = f0_tensor.squeeze(0).numpy()
    periodicity = periodicity_tensor.squeeze(0).numpy()
    return times, f0, periodicity
