"""LAION-CLAP 512-d audio embeddings — lazy singleton, CPU inference."""
from __future__ import annotations

import numpy as np

_CLAP_SR = 48000
_CLAP_SAMPLES = 480000  # 10 s at 48 kHz

_model = None  # loaded once per process


def _get_model():
    global _model
    if _model is None:
        import logging
        import warnings
        import laion_clap
        logging.disable(logging.WARNING)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            m = laion_clap.CLAP_Module(enable_fusion=False)
            m.load_ckpt()
        logging.disable(logging.NOTSET)
        _model = m
    return _model


def embed(audio: np.ndarray, sr: int) -> np.ndarray:
    """Return L2-normalized 512-d CLAP embedding for a mono audio clip."""
    embs = embed_batch([(audio, sr)])
    return embs[0]


def embed_batch(clips: list[tuple[np.ndarray, int]]) -> np.ndarray:
    """Embed multiple (audio, sr) mono clips; returns (N, 512) float32 array."""
    import librosa

    batch = []
    for audio, sr in clips:
        y = audio.astype(np.float32)
        if sr != _CLAP_SR:
            y = librosa.resample(y, orig_sr=sr, target_sr=_CLAP_SR)
        if len(y) < _CLAP_SAMPLES:
            y = np.pad(y, (0, _CLAP_SAMPLES - len(y)))
        else:
            y = y[:_CLAP_SAMPLES]
        batch.append(y)

    x = np.stack(batch)  # (N, 480000)
    model = _get_model()
    return model.get_audio_embedding_from_data(x, use_tensor=False).astype(np.float32)


def is_available() -> bool:
    try:
        import laion_clap  # noqa: F401
        return True
    except ImportError:
        return False
