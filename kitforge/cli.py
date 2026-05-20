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

    t0 = time.perf_counter()
    result = build_kit(
        song_path=song_path,
        instrument=instrument,
        note_range=note_range,
        out_path=Path(out),
        config=cfg,
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
