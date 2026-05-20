"""DeepFilterNet3 post-separation denoising — removes residual bleed from isolated stems."""
from __future__ import annotations

from pathlib import Path

import numpy as np

_model_cache: tuple | None = None  # (model, df_state)


def _patch_torchaudio() -> None:
    """
    deepfilternet 0.5.6 imports torchaudio.backend.common.AudioMetaData and torchaudio.info,
    both removed in torchaudio 2.x. Inject compatible stubs before any df.* import.
    """
    import sys
    import types
    import torchaudio

    if "torchaudio.backend.common" in sys.modules:
        return

    backend_mod = types.ModuleType("torchaudio.backend")
    common_mod = types.ModuleType("torchaudio.backend.common")

    class AudioMetaData:
        def __init__(self, sample_rate: int = 44100, **_kw: object) -> None:
            self.sample_rate = sample_rate

    common_mod.AudioMetaData = AudioMetaData
    sys.modules["torchaudio.backend"] = backend_mod
    sys.modules["torchaudio.backend.common"] = common_mod
    torchaudio.backend = backend_mod  # type: ignore[attr-defined]
    backend_mod.common = common_mod  # type: ignore[attr-defined]

    if not hasattr(torchaudio, "info"):
        import soundfile as sf

        def _info(path: str, **_kw: object) -> AudioMetaData:
            return AudioMetaData(sample_rate=sf.info(path).samplerate)

        torchaudio.info = _info  # type: ignore[attr-defined]


def _get_model() -> tuple:
    global _model_cache
    if _model_cache is None:
        import logging
        import warnings

        _patch_torchaudio()
        logging.disable(logging.WARNING)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            from df.enhance import init_df
            model, df_state, _ = init_df(
                log_level="ERROR",
                log_file=None,
                config_allow_defaults=True,
            )
        logging.disable(logging.NOTSET)
        _model_cache = (model, df_state)
    return _model_cache


def denoise(audio: np.ndarray, sr: int) -> np.ndarray:
    """
    Apply DeepFilterNet3 noise suppression to a mono audio clip.

    Returns denoised audio at the same sample rate. Model downloads ~5 MB to
    ~/Library/Caches/DeepFilterNet/ on first call.
    """
    import torch
    import librosa

    model, df_state = _get_model()
    df_sr: int = df_state.sr()

    y = audio.astype(np.float32)
    if sr != df_sr:
        y = librosa.resample(y, orig_sr=sr, target_sr=df_sr)

    t = torch.from_numpy(y).unsqueeze(0)  # [1, T]

    from df.enhance import enhance as _enhance
    enhanced = _enhance(model, df_state, t)  # [1, T]
    result = enhanced.squeeze(0).numpy().astype(np.float32)

    if sr != df_sr:
        result = librosa.resample(result, orig_sr=df_sr, target_sr=sr)

    return result


def denoise_file(src: Path, dst: Path) -> None:
    """Denoise a WAV file in-place (writes to dst, may equal src)."""
    import soundfile as sf

    audio, sr = sf.read(str(src), always_2d=False)
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio
    clean = denoise(mono, sr)
    if audio.ndim > 1:
        clean = np.stack([clean] * audio.shape[1], axis=1)
    sf.write(str(dst), clean, sr, subtype="PCM_24")


def is_available() -> bool:
    try:
        _patch_torchaudio()
        import df  # noqa: F401
        return True
    except Exception:
        return False
