from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import yaml

_LARSNET_DIR = Path.home() / ".cache" / "kitforge" / "larsnet"
_CONFIG_PATH = _LARSNET_DIR / "config.yaml"
_WEIGHTS_DIR = _LARSNET_DIR / "pretrained_larsnet_models"
_ABS_CONFIG_PATH = _LARSNET_DIR / "config_abs.yaml"

# Maps larsnet stem names → our internal drum class names
STEM_MAP = {
    "kick":    "kick",
    "snare":   "snare",
    "toms":    "toms",
    "hihat":   "hihat",
    "cymbals": "cymbals",
}


def _write_abs_config() -> None:
    """Write a copy of config.yaml with absolute weight paths so LarsNet finds them regardless of cwd."""
    with open(_CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)
    for stem in cfg["inference_models"]:
        rel = cfg["inference_models"][stem]
        cfg["inference_models"][stem] = str(_LARSNET_DIR / rel)
    with open(_ABS_CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f)


def is_available() -> bool:
    """Return True if larsnet repo and all 5 weights are present."""
    if not _CONFIG_PATH.exists():
        return False
    for stem in STEM_MAP:
        weight = _WEIGHTS_DIR / stem / f"pretrained_{stem}_unet.pth"
        if not weight.exists():
            return False
    return True


def separate_drum_stem(drum_wav: Path, out_dir: Path) -> dict[str, Path]:
    """
    Run LarsNet on a drum stem WAV. Returns drum class → wav path.
    Raises RuntimeError if weights are not downloaded yet.
    """
    if not is_available():
        raise RuntimeError(
            "LarsNet weights not found. Run:\n"
            "  kitforge setup-larsnet\n"
            "or wait for the background download to finish."
        )

    if str(_LARSNET_DIR) not in sys.path:
        sys.path.insert(0, str(_LARSNET_DIR))

    from larsnet import LarsNet  # type: ignore

    device = "mps" if torch.backends.mps.is_available() else "cpu"

    # LarsNet resolves weight paths relative to cwd; write an absolute-path config to avoid this
    _write_abs_config()

    model = LarsNet(
        wiener_filter=False,
        config=str(_ABS_CONFIG_PATH),
        device=device,
    )

    stems = model(str(drum_wav))

    out_dir.mkdir(parents=True, exist_ok=True)
    stem_paths: dict[str, Path] = {}
    sr = model.sr

    for larsnet_name, our_name in STEM_MAP.items():
        tensor = stems[larsnet_name].cpu()
        audio_np = tensor.numpy().T  # (samples, channels)
        out_path = out_dir / f"{our_name}.wav"
        sf.write(str(out_path), audio_np, sr, subtype="PCM_24")
        stem_paths[our_name] = out_path

    del model
    if torch.backends.mps.is_available():
        torch.mps.empty_cache()

    return stem_paths
