from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class KitForgeConfig(BaseSettings):
    # toml_file removed from model_config, loaded manually in cli.py to avoid
    # the "config key will be ignored" warning when no TOML source is registered
    model_config = SettingsConfigDict(env_prefix="KITFORGE_")

    # Separation
    separator: Literal["htdemucs_ft", "htdemucs_6s", "bs_roformer"] = "htdemucs_ft"
    separator_quality: Literal["fast", "default", "high"] = "default"

    # Paths
    cache_dir: Path = Path.home() / ".cache" / "kitforge"
    models_dir: Path = Path.home() / ".cache" / "kitforge" / "models"

    # Processing
    sample_rate: int = 44100
    onset_pad_ms: int = 10
    tail_detection_db: float = -60.0
    max_pitch_shift_semitones: int = 5
    velocity_buckets: int = 3
    round_robins: int = 3

    # CLAP
    clap_model: str = "music_audioset_epoch_15_esc_90.14.pt"

    # Debug
    debug: bool = Field(default=False)

    def ensure_dirs(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


def load_config(toml_path: Path | None = None, **overrides: object) -> KitForgeConfig:
    """Load config from env vars, optional TOML file, then apply overrides."""
    import tomllib

    kwargs: dict[str, object] = {}

    candidates = [toml_path, Path("kitforge.toml")] if toml_path else [Path("kitforge.toml")]
    for p in candidates:
        if p and p.exists():
            with open(p, "rb") as f:
                kwargs.update(tomllib.load(f))
            break

    kwargs.update(overrides)
    return KitForgeConfig(**kwargs)
