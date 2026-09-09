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
_PITCHER_VERSION = "1.2"      # BS-RoFormer cascade for pitched instruments
_BASIC_PITCH_VERSION = "1.2"  # BS-RoFormer cascade for pitched instruments
_BANQUET_VERSION = "1.1"  # smart query window + clean instrumental input
_DENOISE_VERSION = "1.0"
_ROFORMER_VERSION = "1.0"


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


def _stems_cached(stems_dir: Path, song_hash: str, expected: list[str], pipeline_tag: str) -> bool:
    sentinel = stems_dir / ".song_hash"
    expected_sentinel = f"{song_hash}\t{pipeline_tag}"
    if not sentinel.exists() or sentinel.read_text().strip() != expected_sentinel:
        return False
    return all((stems_dir / f"{s}.wav").exists() for s in expected)


def build_kit(
    song_path: Path,
    instrument: str,
    note_range: str,
    out_path: Path,
    config: KitForgeConfig,
    query_window: tuple[float, float] | None = None,
) -> PipelineResult:
    """Orchestrate the full separation → extract → package pipeline."""
    from kitforge.cache import StageCache, cache_key

    result = PipelineResult()
    instrument_lower = instrument.lower().strip()
    stage_cache = StageCache(config.cache_dir / "stage_cache")

    # ── Stage 1: Source separation ──────────────────────────────────────────
    song_hash = _file_sha256(song_path)
    is_pitched_nondrum = (
        instrument_lower in _BASS_INSTRUMENTS or instrument_lower in _PITCHED_INSTRUMENTS
    )
    six_stem = instrument_lower in _GUITAR_INSTRUMENTS | _PIANO_INSTRUMENTS
    stems_dir = config.cache_dir / "stems" / song_path.stem

    if six_stem:
        expected_stems = ["drums", "bass", "vocals", "guitar", "piano", "other"]
    else:
        expected_stems = ["drums", "bass", "vocals", "other"]

    # ── Stage 1a (pitched only): BS-RoFormer vocal pre-removal ──────────────
    # Replaces the raw mix with a vocal-stripped instrumental before htdemucs.
    # BS-RoFormer hits ~17 dB instrumental SDR vs htdemucs's ~14 dB, which
    # massively reduces vocal bleed in the "other" stem.
    htdemucs_input = song_path
    if is_pitched_nondrum:
        from kitforge.separation import roformer_runner
        if roformer_runner.is_available():
            t1a = time.perf_counter()
            console.print("[bold blue]Stage 1a:[/bold blue] BS-RoFormer vocal removal...")
            try:
                roformer_out = roformer_runner.separate_vocals(song_path, stems_dir)
                htdemucs_input = roformer_out["instrumental"]
                console.print(f"  [dim]roformer: {time.perf_counter()-t1a:.1f}s[/dim]")
            except Exception as e:
                console.print(f"  [yellow]BS-RoFormer failed ({e}); falling back to raw mix[/yellow]")

    pipeline_tag = f"roformer={htdemucs_input != song_path}/6s={six_stem}"

    t1 = time.perf_counter()
    if _stems_cached(stems_dir, song_hash, expected_stems, pipeline_tag):
        console.print("[bold blue]Stage 1/3:[/bold blue] Stems cached — skipping separation")
        stem_paths = {s: stems_dir / f"{s}.wav" for s in expected_stems}
    else:
        console.print("[bold blue]Stage 1/3:[/bold blue] Separating stems...")
        from kitforge.separation.demucs_runner import separate
        stem_paths = separate(
            audio_path=htdemucs_input,
            out_dir=stems_dir,
            quality=config.separator_quality,
            six_stem=six_stem,
        )
        (stems_dir / ".song_hash").write_text(f"{song_hash}\t{pipeline_tag}")
    console.print(f"  [dim]separation: {time.perf_counter()-t1:.1f}s[/dim]")

    # ── Stage 2: Extract samples ─────────────────────────────────────────────
    t2 = time.perf_counter()
    console.print("[bold blue]Stage 2/3:[/bold blue] Extracting samples...")
    sample_dir = out_path if out_path.suffix == "" else out_path.parent / out_path.stem
    sample_dir.mkdir(parents=True, exist_ok=True)

    if instrument_lower in _DRUM_INSTRUMENTS:
        from kitforge.extract.slicer import slice_drum_stem

        drum_wav = stem_paths["drums"]
        if config.separator_quality == "high":
            drum_wav = _denoise_stem(drum_wav, stems_dir, stage_cache, config.debug)

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
        if config.separator_quality == "high":
            bass_wav = _denoise_stem(bass_wav, stems_dir, stage_cache, config.debug)

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

        # Optional Banquet refinement — only when --quality high
        # (CPU inference ~35 min/song; CUDA ~5 min)
        from kitforge.separation import query_separator
        if config.separator_quality == "high" and query_separator.is_available():
            stem_wav = _banquet_refine(
                mixture_path=htdemucs_input,  # vocal-stripped instrumental
                rough_stem=stem_wav,
                song_path=song_path,
                query_window=query_window,
                instrument=instrument_lower,
                stems_dir=stems_dir,
                stage_cache=stage_cache,
                debug=config.debug,
            )
            if config.debug:
                console.print(f"  [dim]banquet: using refined stem {stem_wav.name}[/dim]")
        elif config.separator_quality == "high" and not query_separator.is_available():
            console.print(
                "  [dim](tip: run 'kitforge setup-banquet' for even better quality at --quality high)[/dim]"
            )

        if config.separator_quality == "high":
            stem_wav = _denoise_stem(stem_wav, stems_dir, stage_cache, config.debug)

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

def _banquet_refine(
    mixture_path: Path,
    rough_stem: Path,
    song_path: Path,
    query_window: tuple[float, float] | None,
    instrument: str,
    stems_dir: Path,
    stage_cache,
    debug: bool,
) -> Path:
    """
    Run Banquet query separation on a vocal-stripped instrumental.

    mixture_path:  the audio Banquet operates on (BS-RoFormer instrumental)
    rough_stem:    the htdemucs stem used to auto-pick a query window
    song_path:     the original mix (only used when query_window is given)
    query_window:  (start_s, end_s) in the ORIGINAL song, or None to auto-pick
    """
    from kitforge.separation import query_separator
    from kitforge.cache import cache_key

    qtag = "user" if query_window else "auto"
    ck = cache_key(mixture_path, f"banquet_{instrument}_{qtag}", _BANQUET_VERSION, {})
    refined_path = stems_dir / f"banquet_{instrument.replace(' ', '_')}.wav"

    if refined_path.exists() and stage_cache.has(ck):
        return refined_path

    import soundfile as sf
    import numpy as np

    query_path = stems_dir / f"_query_{instrument.replace(' ', '_')}.wav"

    if query_window is not None:
        # User-specified: clip from the ORIGINAL song so the target timbre is exact
        data, sr = sf.read(str(song_path), always_2d=True)
        s0 = max(0, int(query_window[0] * sr))
        s1 = min(len(data), int(query_window[1] * sr))
        query_clip = data[s0:s1]
        if debug:
            console.print(f"  [dim]banquet query: user {query_window[0]:.1f}-{query_window[1]:.1f}s from song[/dim]")
    else:
        # Auto-pick: highest-RMS 10s window of the rough stem (avoids sparse intros)
        data, sr = sf.read(str(rough_stem), always_2d=True)
        s0, s1 = _best_query_window(data, sr, win_s=10.0)
        query_clip = data[s0:s1]
        if debug:
            console.print(f"  [dim]banquet query: auto {s0/sr:.1f}-{s1/sr:.1f}s from rough stem[/dim]")

    sf.write(str(query_path), query_clip, sr)

    console.print(f"  Running Banquet separation for {instrument}...")
    try:
        query_separator.separate(
            audio_path=mixture_path,
            query_wav_path=query_path,
            out_path=refined_path,
            instrument=instrument,
        )
        stage_cache.set(ck, str(refined_path))
    except ValueError as e:
        # Audio too short for Banquet — fall back to htdemucs stem
        if debug:
            console.print(f"  [dim]Banquet skipped: {e}[/dim]")
        return rough_stem
    finally:
        query_path.unlink(missing_ok=True)

    return refined_path


def _best_query_window(data, sr: int, win_s: float = 10.0) -> tuple[int, int]:
    """Find the start/end sample indices of the highest-RMS win_s-second window."""
    import numpy as np

    mono = data.mean(axis=1) if data.ndim > 1 else data
    win = int(win_s * sr)
    if len(mono) <= win:
        return 0, len(mono)

    # Stride at 1s — cheap, plenty fine
    hop = sr
    rms_scores = []
    for start in range(0, len(mono) - win + 1, hop):
        chunk = mono[start:start + win]
        rms_scores.append((np.sqrt(np.mean(chunk * chunk)), start))
    _, best_start = max(rms_scores, key=lambda t: t[0])
    return best_start, best_start + win


def _denoise_stem(
    stem_wav: Path,
    stems_dir: Path,
    stage_cache,
    debug: bool,
) -> Path:
    """
    Run DeepFilterNet3 on stem_wav and write the result next to the original stem.
    Returns the denoised stem path; returns the original on any error.
    """
    from kitforge.extract.denoise import denoise_file, is_available
    from kitforge.cache import cache_key

    if not is_available():
        return stem_wav

    denoised_path = stems_dir / f"denoised_{stem_wav.name}"
    ck = cache_key(stem_wav, "deepfilter3", _DENOISE_VERSION, {})

    if denoised_path.exists() and stage_cache.has(ck):
        if debug:
            console.print(f"  [dim]denoise: cached {denoised_path.name}[/dim]")
        return denoised_path

    console.print(f"  [dim]DeepFilterNet: denoising {stem_wav.name}...[/dim]")
    try:
        denoise_file(stem_wav, denoised_path)
        stage_cache.set(ck, str(denoised_path))
    except Exception as e:
        if debug:
            console.print(f"  [dim]denoise failed: {e}[/dim]")
        return stem_wav

    return denoised_path


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
