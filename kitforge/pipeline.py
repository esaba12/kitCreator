from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from kitforge.config import KitForgeConfig

console = Console()

_DRUM_INSTRUMENTS = {"drums", "drum", "kit", "drum kit"}
_BASS_INSTRUMENTS = {"bass", "bass guitar", "synth bass", "808"}


@dataclass
class PipelineResult:
    sfz_path: Path | None = None
    dspreset_path: Path | None = None
    sample_dir: Path | None = None
    warnings: list[str] = field(default_factory=list)


def build_kit(
    song_path: Path,
    instrument: str,
    note_range: str,
    out_path: Path,
    config: KitForgeConfig,
) -> PipelineResult:
    """Orchestrate the full separation → extract → package pipeline."""
    result = PipelineResult()
    instrument_lower = instrument.lower().strip()

    # ── Stage 1: Source separation ──────────────────────────────────────────
    console.print("[bold blue]Stage 1/3:[/bold blue] Separating stems...")
    from kitforge.separation.demucs_runner import separate

    six_stem = instrument_lower in ("guitar", "piano")
    stems_dir = config.cache_dir / "stems" / song_path.stem
    stem_paths = separate(
        audio_path=song_path,
        out_dir=stems_dir,
        quality=config.separator_quality,
        six_stem=six_stem,
    )
    console.print(f"  stems → {stems_dir}")

    # ── Stage 2: Extract samples ─────────────────────────────────────────────
    console.print("[bold blue]Stage 2/3:[/bold blue] Extracting samples...")
    if instrument_lower in _DRUM_INSTRUMENTS:
        from kitforge.extract.slicer import slice_drum_stem
        sample_dir = out_path if out_path.suffix == "" else out_path.parent / out_path.stem
        sample_dir.mkdir(parents=True, exist_ok=True)
        one_shots = slice_drum_stem(stem_paths["drums"], sample_dir, debug=config.debug)
        result.sample_dir = sample_dir
    else:
        raise NotImplementedError(f"Instrument '{instrument}' not yet supported — only 'drums' is implemented in Phase 1.1")

    # ── Stage 3: Package ─────────────────────────────────────────────────────
    console.print("[bold blue]Stage 3/3:[/bold blue] Writing SFZ and DecentSampler preset...")
    from kitforge.package.sfz_writer import write_drum_sfz
    from kitforge.package.decentsampler_writer import write_drum_dspreset

    sfz_path = sample_dir / "kit.sfz"
    dspreset_path = sample_dir / "kit.dspreset"
    write_drum_sfz(one_shots, sfz_path)
    write_drum_dspreset(one_shots, dspreset_path)

    result.sfz_path = sfz_path
    result.dspreset_path = dspreset_path

    if not one_shots:
        result.warnings.append("No one-shots detected — try a song with a clearer drum part")

    return result
