from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

app = typer.Typer(name="kitforge", help="Turn any song into a playable sampler kit.")
console = Console()

_SUPPORTED_FORMATS = {".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a", ".ogg"}

_CONSENT_BANNER = (
    "[yellow]kitforge may produce derivative works of copyrighted recordings.\n"
    "You are responsible for clearing samples before any commercial release.[/yellow]"
)


@app.callback()
def _callback() -> None:
    console.print(_CONSENT_BANNER)


@app.command()
def build(
    song: str = typer.Option(..., "--song", help="Path to source audio file (.mp3, .wav, .flac, .aiff, .m4a, .ogg)"),
    instrument: str = typer.Option(..., "--instrument", help='Target instrument, e.g. "drums", "bass", "lead synth"'),
    note_range: str = typer.Option("C2-C7", "--range", help="MIDI note range to fill, e.g. C2-C7"),
    out: str = typer.Option("kit.sfz", "--out", help="Output path (.sfz file or directory for drums)"),
    quality: str = typer.Option("default", "--quality", help="Separation quality: fast | default | high"),
    debug: bool = typer.Option(False, "--debug", help="Write intermediate WAVs and CLAP t-SNE plots"),
    config: str = typer.Option(None, "--config", help="Path to TOML config file"),
) -> None:
    """Build a sampler kit from a song."""
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

    out_path = Path(out)

    console.print(
        f"[bold]Building kit[/bold] — "
        f"song=[cyan]{song_path.name}[/cyan] "
        f"instrument=[cyan]{instrument}[/cyan] "
        f"range={note_range} quality={quality}"
    )

    from kitforge.config import KitForgeConfig
    from kitforge.pipeline import build_kit

    cfg = KitForgeConfig()
    if debug:
        cfg.debug = True
    cfg.ensure_dirs()

    result = build_kit(
        song_path=song_path,
        instrument=instrument,
        note_range=note_range,
        out_path=out_path,
        config=cfg,
    )

    if result.sfz_path:
        console.print(f"[green]SFZ written:[/green] {result.sfz_path}")
    if result.dspreset_path:
        console.print(f"[green]DecentSampler preset written:[/green] {result.dspreset_path}")
    for warning in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {warning}")


if __name__ == "__main__":
    app()
