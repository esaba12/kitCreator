from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.console import Console

from kitforge.config import KitForgeConfig

console = Console()

_DRUM_INSTRUMENTS = {"drums", "drum", "kit", "drum kit"}
_BASS_INSTRUMENTS = {"bass", "bass guitar", "808"}
_GUITAR_INSTRUMENTS = {"guitar", "electric guitar", "acoustic guitar"}
_PIANO_INSTRUMENTS = {"piano", "keys", "keyboard", "electric piano", "rhodes"}
_SYNTH_INSTRUMENTS = {"synth", "lead synth", "synth bass", "lead", "pad", "organ", "synth lead"}
_PITCHED_INSTRUMENTS = _GUITAR_INSTRUMENTS | _PIANO_INSTRUMENTS | _SYNTH_INSTRUMENTS

# Default MIDI ranges per instrument family
_DEFAULT_RANGES: dict[str, tuple[int, int]] = {
    "guitar": (40, 88),   # E2–E6
    "piano":  (36, 96),   # C2–C7
    "synth":  (48, 84),   # C3–C6
}

# Bump these when the corresponding stage logic changes to bust cached results
_SLICER_VERSION = "1.1"
_PITCHER_VERSION = "1.0"
_BASIC_PITCH_VERSION = "1.0"


@dataclass
class PipelineResult:
    sfz_path: Path | None = None
    dspreset_path: Path | None = None
    sample_dir: Path | None = None
    warnings: list[str] = field(default_factory=list)


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _stems_cached(stems_dir: Path, song_hash: str, expected: list[str]) -> bool:
    sentinel = stems_dir / ".song_hash"
    if not sentinel.exists() or sentinel.read_text().strip() != song_hash:
        return False
    return all((stems_dir / f"{s}.wav").exists() for s in expected)


def build_kit(
    song_path: Path,
    instrument: str,
    note_range: str,
    out_path: Path,
    config: KitForgeConfig,
) -> PipelineResult:
    """Orchestrate the full separation → extract → package pipeline."""
    from kitforge.cache import StageCache, cache_key

    result = PipelineResult()
    instrument_lower = instrument.lower().strip()
    stage_cache = StageCache(config.cache_dir / "stage_cache")

    # ── Stage 1: Source separation ──────────────────────────────────────────
    song_hash = _file_sha256(song_path)
    six_stem = instrument_lower in _GUITAR_INSTRUMENTS | _PIANO_INSTRUMENTS
    stems_dir = config.cache_dir / "stems" / song_path.stem

    if six_stem:
        expected_stems = ["drums", "bass", "vocals", "guitar", "piano", "other"]
    else:
        expected_stems = ["drums", "bass", "vocals", "other"]

    t1 = time.perf_counter()
    if _stems_cached(stems_dir, song_hash, expected_stems):
        console.print("[bold blue]Stage 1/3:[/bold blue] Stems cached — skipping separation")
        stem_paths = {s: stems_dir / f"{s}.wav" for s in expected_stems}
    else:
        console.print("[bold blue]Stage 1/3:[/bold blue] Separating stems...")
        from kitforge.separation.demucs_runner import separate
        stem_paths = separate(
            audio_path=song_path,
            out_dir=stems_dir,
            quality=config.separator_quality,
            six_stem=six_stem,
        )
        (stems_dir / ".song_hash").write_text(song_hash)
    console.print(f"  [dim]separation: {time.perf_counter()-t1:.1f}s[/dim]")

    # ── Stage 2: Extract samples ─────────────────────────────────────────────
    t2 = time.perf_counter()
    console.print("[bold blue]Stage 2/3:[/bold blue] Extracting samples...")
    sample_dir = out_path if out_path.suffix == "" else out_path.parent / out_path.stem
    sample_dir.mkdir(parents=True, exist_ok=True)

    if instrument_lower in _DRUM_INSTRUMENTS:
        from kitforge.extract.slicer import slice_drum_stem

        drum_wav = stem_paths["drums"]
        slicer_params = {
            "rr": config.round_robins,
            "vel_buckets": config.velocity_buckets,
            "tail_db": config.tail_detection_db,
            "out": str(sample_dir),
        }
        ck = cache_key(drum_wav, "drum_slicer", _SLICER_VERSION, slicer_params)

        if stage_cache.has(ck) and _cached_files_exist(stage_cache.get(ck)):
            console.print("  samples cached — skipping slicing")
            one_shots = stage_cache.get(ck)
        else:
            one_shots = slice_drum_stem(drum_wav, sample_dir, debug=config.debug)
            stage_cache.set(ck, one_shots)

        result.sample_dir = sample_dir
        console.print(f"  [dim]extraction: {time.perf_counter()-t2:.1f}s — {len(one_shots)} one-shots[/dim]")

        # ── Stage 3: Package ─────────────────────────────────────────────────
        t3 = time.perf_counter()
        console.print("[bold blue]Stage 3/3:[/bold blue] Writing SFZ and DecentSampler preset...")
        from kitforge.package.sfz_writer import write_drum_sfz
        from kitforge.package.decentsampler_writer import write_drum_dspreset

        sfz_path = sample_dir / "kit.sfz"
        dspreset_path = sample_dir / "kit.dspreset"
        write_drum_sfz(one_shots, sfz_path)
        write_drum_dspreset(one_shots, dspreset_path)

        result.sfz_path = sfz_path
        result.dspreset_path = dspreset_path
        console.print(f"  [dim]packaging: {time.perf_counter()-t3:.1f}s[/dim]")

        if not one_shots:
            result.warnings.append("No one-shots detected — try a song with a clearer drum part")

    elif instrument_lower in _BASS_INSTRUMENTS:
        from kitforge.extract.pitched_slicer import slice_bass_stem

        bass_wav = stem_paths["bass"]
        lo_midi, hi_midi = _parse_note_range(note_range, default=(24, 67))  # C1–G4
        pitcher_params = {
            "lo": lo_midi,
            "hi": hi_midi,
            "out": str(sample_dir),
        }
        ck = cache_key(bass_wav, "bass_pitcher", _PITCHER_VERSION, pitcher_params)

        if stage_cache.has(ck) and _cached_files_exist(stage_cache.get(ck)):
            console.print("  samples cached — skipping pitch extraction")
            shots = stage_cache.get(ck)
        else:
            shots = slice_bass_stem(
                bass_wav, sample_dir,
                note_range=(lo_midi, hi_midi),
                debug=config.debug,
            )
            stage_cache.set(ck, shots)

        result.sample_dir = sample_dir
        console.print(f"  [dim]extraction: {time.perf_counter()-t2:.1f}s — {len(shots)} zones[/dim]")

        # ── Stage 3: Package ─────────────────────────────────────────────────
        t3 = time.perf_counter()
        console.print("[bold blue]Stage 3/3:[/bold blue] Writing SFZ and DecentSampler preset...")
        from kitforge.package.sfz_writer import write_pitched_sfz
        from kitforge.package.decentsampler_writer import write_pitched_dspreset

        sfz_path = sample_dir / "kit.sfz"
        dspreset_path = sample_dir / "kit.dspreset"
        write_pitched_sfz(shots, sfz_path)
        write_pitched_dspreset(shots, dspreset_path)

        result.sfz_path = sfz_path
        result.dspreset_path = dspreset_path
        console.print(f"  [dim]packaging: {time.perf_counter()-t3:.1f}s[/dim]")

        if not shots:
            result.warnings.append("No bass notes detected — check that the song has a clear bass part")

    elif instrument_lower in _PITCHED_INSTRUMENTS:
        from kitforge.transcribe.basic_pitch_runner import transcribe
        from kitforge.extract.pitched_slicer import slice_pitched_stem

        # Pick stem and default range by instrument family
        if instrument_lower in _GUITAR_INSTRUMENTS:
            stem_wav = stem_paths.get("guitar", stem_paths["other"])
            family = "guitar"
        elif instrument_lower in _PIANO_INSTRUMENTS:
            stem_wav = stem_paths.get("piano", stem_paths["other"])
            family = "piano"
        else:
            stem_wav = stem_paths["other"]
            family = "synth"

        lo_midi, hi_midi = _parse_note_range(note_range, default=_DEFAULT_RANGES[family])

        bp_params = {"lo": lo_midi, "hi": hi_midi, "out": str(sample_dir), "stem": str(stem_wav)}
        ck = cache_key(stem_wav, f"basic_pitch_{family}", _BASIC_PITCH_VERSION, bp_params)

        if stage_cache.has(ck) and _cached_files_exist(stage_cache.get(ck)):
            console.print("  samples cached — skipping transcription")
            shots = stage_cache.get(ck)
        else:
            note_events = transcribe(stem_wav)
            if config.debug:
                print(f"  {family}: {len(note_events)} note events from Basic Pitch")
            shots = slice_pitched_stem(
                stem_wav, note_events, sample_dir,
                note_range=(lo_midi, hi_midi),
                debug=config.debug,
            )
            stage_cache.set(ck, shots)

        result.sample_dir = sample_dir
        console.print(f"  [dim]extraction: {time.perf_counter()-t2:.1f}s — {len(shots)} zones[/dim]")

        # ── Stage 3: Package ─────────────────────────────────────────────────
        t3 = time.perf_counter()
        console.print("[bold blue]Stage 3/3:[/bold blue] Writing SFZ and DecentSampler preset...")
        from kitforge.package.sfz_writer import write_pitched_sfz
        from kitforge.package.decentsampler_writer import write_pitched_dspreset

        sfz_path = sample_dir / "kit.sfz"
        dspreset_path = sample_dir / "kit.dspreset"
        write_pitched_sfz(shots, sfz_path)
        write_pitched_dspreset(shots, dspreset_path)

        result.sfz_path = sfz_path
        result.dspreset_path = dspreset_path
        console.print(f"  [dim]packaging: {time.perf_counter()-t3:.1f}s[/dim]")

        if not shots:
            result.warnings.append(
                f"No {family} notes detected — try a song with a clearer {family} part, "
                "or check that the stem contains the expected instrument"
            )

    else:
        raise NotImplementedError(
            f"Instrument '{instrument}' not yet supported. "
            "Supported: drums, bass, guitar, piano, synth, lead synth"
        )

    return result


# ── helpers ──────────────────────────────────────────────────────────────────

def _cached_files_exist(shots: list | None) -> bool:
    """Verify that all sample files referenced by a cached shot list still exist."""
    if not shots:
        return False
    return all(s.path.exists() for s in shots)


def _parse_note_range(range_str: str, default: tuple[int, int]) -> tuple[int, int]:
    """Parse 'C2-C5' or 'E1-G4' into (lo_midi, hi_midi). Falls back to default."""
    import re
    import librosa

    if not range_str:
        return default

    m = re.fullmatch(r"([A-Ga-g][#b]?\d)\s*[-–]\s*([A-Ga-g][#b]?\d)", range_str.strip())
    if not m:
        return default

    try:
        lo = int(librosa.note_to_midi(m.group(1)))
        hi = int(librosa.note_to_midi(m.group(2)))
        return (lo, hi) if lo <= hi else (hi, lo)
    except Exception:
        return default
