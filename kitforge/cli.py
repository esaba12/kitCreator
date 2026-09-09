from __future__ import annotations

import time
import warnings
from pathlib import Path

import typer
from rich.console import Console

# Suppress cosmetic third-party warnings that aren't actionable
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
warnings.filterwarnings("ignore", message="Config key `toml_file`")
warnings.filterwarnings("ignore", message="An output with one or more elements was resized")

app = typer.Typer(name="kitforge", add_completion=False, help="Turn any song into a playable sampler kit.")
console = Console()


@app.callback()
def _root() -> None:
    """kitforge — turn any song into a playable sampler kit."""

_SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a", ".ogg"}

_CONSENT_BANNER = (
    "[dim yellow]kitforge may produce derivative works of copyrighted recordings. "
    "You are responsible for clearing samples before any commercial release.[/dim yellow]"
)

_CONSENT_SENTINEL_NAME = ".consent_shown"


def _show_consent_once(cache_dir: Path) -> None:
    sentinel = cache_dir / _CONSENT_SENTINEL_NAME
    if not sentinel.exists():
        console.print(_CONSENT_BANNER)
        cache_dir.mkdir(parents=True, exist_ok=True)
        sentinel.touch()


@app.command()
def build(
    song: str = typer.Option(..., "--song", help="Path to source audio (.mp3 .wav .flac .aiff .m4a .ogg)"),
    instrument: str = typer.Option(..., "--instrument", help='Instrument: "drums", "bass", "lead synth", …'),
    note_range: str = typer.Option("", "--range", help="MIDI range to fill, e.g. C2-C7 (pitched instruments only)"),
    out: str = typer.Option("kit", "--out", help="Output directory"),
    quality: str = typer.Option("default", "--quality", help="Separation quality: fast | default | high"),
    debug: bool = typer.Option(False, "--debug/--no-debug", help="Write intermediate WAVs and extra diagnostics"),
    config_file: str = typer.Option(None, "--config", help="Path to TOML config file"),
    mc101: str = typer.Option(None, "--mc101", help="Path to MC-101 SD card root (e.g. /Volumes/MC101)"),
    query: str = typer.Option(None, "--query", help="Banquet query window in the song, e.g. 0:34-0:44 (--quality high only)"),
) -> None:
    """Build a sampler kit from a song."""
    from kitforge.config import load_config
    from kitforge.pipeline import build_kit

    song_path = Path(song)

    if not song_path.exists():
        console.print(f"[red]File not found:[/red] {song_path}")
        raise typer.Exit(1)

    if song_path.suffix.lower() not in _SUPPORTED_FORMATS:
        supported = ", ".join(sorted(_SUPPORTED_FORMATS))
        console.print(f"[red]Unsupported format[/red] '{song_path.suffix}'. Supported: {supported}")
        raise typer.Exit(1)

    if quality not in ("fast", "default", "high"):
        console.print("[red]--quality must be fast, default, or high[/red]")
        raise typer.Exit(1)

    cfg = load_config(
        toml_path=Path(config_file) if config_file else None,
        separator_quality=quality,
        debug=debug,
    )

    _show_consent_once(cfg.cache_dir)
    cfg.ensure_dirs()

    console.print(
        f"[bold]Building kit[/bold] — "
        f"song=[cyan]{song_path.name}[/cyan] "
        f"instrument=[cyan]{instrument}[/cyan]"
        + (f" range=[cyan]{note_range}[/cyan]" if note_range else "")
        + f" quality=[cyan]{quality}[/cyan]"
    )

    query_window = _parse_query_window(query) if query else None
    if query and query_window is None:
        console.print(f"[red]Invalid --query '{query}'. Use MM:SS-MM:SS, e.g. 0:34-0:44[/red]")
        raise typer.Exit(1)

    t0 = time.perf_counter()
    result = build_kit(
        song_path=song_path,
        instrument=instrument,
        note_range=note_range,
        out_path=Path(out),
        config=cfg,
        query_window=query_window,
    )
    elapsed = time.perf_counter() - t0

    # ── End-of-run summary ────────────────────────────────────────────────────
    sample_count = 0
    if result.sample_dir and (result.sample_dir / "samples").exists():
        sample_count = len(list((result.sample_dir / "samples").glob("*.wav")))

    console.print()
    console.print(f"[bold green]Done[/bold green] in {elapsed:.1f}s — {sample_count} samples")
    if result.sfz_path:
        console.print(f"  [green]SFZ[/green]           {result.sfz_path}")
    if result.dspreset_path:
        console.print(f"  [green]DecentSampler[/green] {result.dspreset_path}")
    if result.sample_dir:
        console.print(f"  [green]Samples dir[/green]   {result.sample_dir / 'samples'}")

    for warning in result.warnings:
        console.print(f"\n[yellow]Warning:[/yellow] {warning}")

    if mc101:
        _export_mc101(mc101, song_path, instrument, result)


def _parse_query_window(s: str) -> tuple[float, float] | None:
    """Parse 'MM:SS-MM:SS' or 'SS-SS' into (start_s, end_s)."""
    import re
    m = re.fullmatch(r"\s*(\d+:)?(\d+(?:\.\d+)?)\s*-\s*(\d+:)?(\d+(?:\.\d+)?)\s*", s)
    if not m:
        return None
    def _to_sec(mins: str | None, secs: str) -> float:
        mins_f = float(mins[:-1]) if mins else 0.0
        return mins_f * 60.0 + float(secs)
    start = _to_sec(m.group(1), m.group(2))
    end   = _to_sec(m.group(3), m.group(4))
    return (start, end) if end > start else None


def _export_mc101(mc101_str: str, song_path: Path, instrument: str, result) -> None:
    from kitforge.package.mc101_writer import export_drums, export_pitched

    sd_root = Path(mc101_str)
    if not sd_root.exists():
        console.print(f"[red]MC-101 path not found:[/red] {sd_root}")
        return

    kit_name = song_path.stem
    instrument_lower = instrument.lower().strip()

    console.print()
    console.print("[bold blue]MC-101 export...[/bold blue]")

    # Read shots back from the sample dir to avoid threading pipeline state through
    if instrument_lower in {"drums", "drum", "kit", "drum kit"}:
        if result.sample_dir is None:
            console.print("[red]No sample dir — cannot export to MC-101[/red]")
            return
        from kitforge.extract.slicer import OneShot
        shots = _load_drum_shots(result.sample_dir)
        if not shots:
            console.print("[yellow]No shots found in sample dir[/yellow]")
            return
        folder = export_drums(shots, kit_name, sd_root)
        console.print(f"  [green]MC-101 drums[/green] → {folder}")
    else:
        if result.sample_dir is None:
            console.print("[red]No sample dir — cannot export to MC-101[/red]")
            return
        shots = _load_pitched_shots(result.sample_dir)
        if not shots:
            console.print("[yellow]No pitched shots found in sample dir[/yellow]")
            return
        folder = export_pitched(shots, instrument_lower, kit_name, sd_root)
        console.print(f"  [green]MC-101 pitched[/green] → {folder}")
    console.print(f"  Read SETUP.txt in {folder} for pad/key assignments.")


def _load_drum_shots(sample_dir: Path):
    """Reconstruct minimal OneShot list from WAV filenames in sample_dir/samples/."""
    from kitforge.extract.slicer import OneShot

    wav_dir = sample_dir / "samples"
    shots = []
    for wav in sorted(wav_dir.glob("*.wav")):
        # filename pattern: {class}_v{vel_low}_{rr_index}.wav  (rr is 1-indexed)
        parts = wav.stem.rsplit("_", 2)
        if len(parts) < 3:
            continue
        drum_class, vel_part, rr_str = parts
        if not vel_part.startswith("v"):
            continue
        try:
            vel_low = int(vel_part[1:])
            rr_index = int(rr_str) - 1  # filenames are 1-indexed; OneShot stores 0-indexed
        except ValueError:
            continue
        shots.append(OneShot(
            path=wav,
            drum_class=drum_class,
            rr_index=rr_index,
            vel_low=vel_low,
            vel_high=vel_low,  # exact value not needed for MC-101 export
        ))
    return shots


def _load_pitched_shots(sample_dir: Path):
    """Reconstruct minimal PitchedShot list from WAV filenames in sample_dir/samples/."""
    from kitforge.extract.pitched_slicer import PitchedShot

    wav_dir = sample_dir / "samples"
    shots = []
    for wav in sorted(wav_dir.glob("*.wav")):
        # filename pattern: bass_{note_name}_midi{midi_note}.wav
        if "_midi" not in wav.stem:
            continue
        try:
            midi_note = int(wav.stem.rsplit("_midi", 1)[1])
        except (ValueError, IndexError):
            continue
        shots.append(PitchedShot(path=wav, midi_note=midi_note, lokey=midi_note, hikey=midi_note))
    return shots


@app.command(name="setup-banquet")
def setup_banquet(
    no_weights: bool = typer.Option(False, "--no-weights", help="Clone repo and install deps only; skip the 646 MB weight download"),
) -> None:
    """Set up Banquet for higher-quality guitar/piano/synth separation."""
    from kitforge.separation import query_separator

    console.print("[bold blue]Setting up Banquet query separation...[/bold blue]")
    query_separator.setup(download_weights=not no_weights)
    console.print("[bold green]Banquet ready.[/bold green] Re-run 'kitforge build' to use improved separation.")


if __name__ == "__main__":
    app()
