"""BS-RoFormer vocal/instrumental separation via python-audio-separator.

Used as a pre-stage before htdemucs on pitched instruments; removes vocals
with ~17 dB instrumental SDR, far above htdemucs's ~14 dB.
"""
from __future__ import annotations

import os
from pathlib import Path

# SOTA BS-RoFormer checkpoint: vocals SDR 12.9, instrumental SDR 17.0
_ROFORMER_MODEL = "model_bs_roformer_ep_317_sdr_12.9755.ckpt"

_model_singleton = None


def is_available() -> bool:
    try:
        from audio_separator.separator import Separator  # noqa: F401
        return True
    except ImportError:
        return False


def _get_separator(out_dir: Path):
    global _model_singleton
    if _model_singleton is not None:
        return _model_singleton

    from audio_separator.separator import Separator

    out_dir.mkdir(parents=True, exist_ok=True)
    sep = Separator(
        output_dir=str(out_dir),
        output_format="WAV",
        log_level=40,  # ERROR, silence the noisy info logs
    )
    sep.load_model(model_filename=_ROFORMER_MODEL)
    _model_singleton = sep
    return sep


def separate_vocals(audio_path: Path, out_dir: Path) -> dict[str, Path]:
    """Run BS-RoFormer to split a mix into vocals + instrumental.

    Returns {"vocals": Path, "instrumental": Path}.
    Files are cached at out_dir / roformer_{vocals,instrumental}.wav.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    vocals_path = out_dir / "roformer_vocals.wav"
    instrumental_path = out_dir / "roformer_instrumental.wav"

    if vocals_path.exists() and instrumental_path.exists():
        return {"vocals": vocals_path, "instrumental": instrumental_path}

    sep = _get_separator(out_dir)

    audio_path = Path(audio_path).resolve()
    cwd = os.getcwd()
    try:
        os.chdir(out_dir)
        output_files = sep.separate(str(audio_path))
    finally:
        os.chdir(cwd)

    # audio-separator names outputs like "<stem>_(Vocals)_<model>.wav"
    for out_file in output_files:
        p = out_dir / out_file if not Path(out_file).is_absolute() else Path(out_file)
        if not p.exists():
            continue
        name_lower = p.name.lower()
        if "(vocals)" in name_lower or "_vocals" in name_lower:
            p.rename(vocals_path)
        elif "(instrumental)" in name_lower or "_instrumental" in name_lower:
            p.rename(instrumental_path)

    if not (vocals_path.exists() and instrumental_path.exists()):
        raise RuntimeError(
            f"BS-RoFormer output naming unexpected; got: {output_files}"
        )

    return {"vocals": vocals_path, "instrumental": instrumental_path}
