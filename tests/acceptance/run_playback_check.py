#!/usr/bin/env python
"""Headless "does this kit actually play" acceptance check, via sfizz_render.

Usage:
  python tests/acceptance/run_playback_check.py --kit-dir site/demo/assets/drums
  python tests/acceptance/run_playback_check.py --song assets/test_audio/test_mix.wav \\
      --instrument drums --out /tmp/kit_check

Verifies only the .sfz half of a kit's paired SFZ/DecentSampler output --
DecentSampler's .dspreset format has no known headless renderer, so it stays
unverified by this check (see tests/acceptance/README.md).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.acceptance.generate_test_midi import build_drum_midi, build_pitched_midi
from tests.acceptance.sfizz_binary import find_sfizz_render
from tests.acceptance.sfz_parser import parse_regions
from tests.acceptance.verify_render import verify


def _detect_kind(regions) -> str:
    """Drum regions always have lokey==hikey (one fixed note per class); pitched
    regions span a zone. A single pitched note zone that happens to collapse to
    lokey==hikey would be misdetected -- pass --kind explicitly for that case."""
    if any(r.int("lokey") != r.int("hikey") for r in regions):
        return "pitched"
    return "drum"


def build_kit(song: Path, instrument: str, out_dir: Path) -> Path:
    cmd = [
        sys.executable, "-m", "kitforge.cli", "build",
        "--song", str(song), "--instrument", instrument, "--out", str(out_dir),
    ]
    print(f"  building kit: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        sys.exit(f"kitforge build failed (exit {result.returncode})")
    return out_dir / "kit.sfz"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit-dir", help="Directory containing an already-built kit.sfz")
    parser.add_argument("--song", help="Song to build a kit from (requires --instrument --out)")
    parser.add_argument("--instrument", help="Instrument to build, e.g. drums, bass")
    parser.add_argument("--out", help="Output directory for a fresh kitforge build")
    parser.add_argument("--kind", choices=["auto", "drum", "pitched"], default="auto")
    parser.add_argument("--samplerate", type=int, default=44100)
    args = parser.parse_args()

    if args.kit_dir:
        sfz_path = Path(args.kit_dir) / "kit.sfz"
    elif args.song and args.instrument and args.out:
        sfz_path = build_kit(Path(args.song), args.instrument, Path(args.out))
    else:
        parser.error("pass --kit-dir, or all of --song/--instrument/--out")
        return

    if not sfz_path.is_file():
        sys.exit(f"no kit.sfz at {sfz_path}")

    regions = parse_regions(sfz_path)
    if not regions:
        sys.exit(f"no <region> opcodes parsed from {sfz_path}")

    kind = args.kind if args.kind != "auto" else _detect_kind(regions)
    print(f"  kit: {sfz_path} ({len(regions)} regions, kind={kind})")

    if kind == "drum":
        pm, events = build_drum_midi(regions)
    else:
        pm, events = build_pitched_midi(regions)

    sfizz_render = find_sfizz_render()

    with tempfile.TemporaryDirectory() as scratch:
        midi_path = Path(scratch) / "test.mid"
        wav_path = Path(scratch) / "render.wav"
        pm.write(str(midi_path))

        cmd = [
            str(sfizz_render),
            "--sfz", str(sfz_path),
            "--midi", str(midi_path),
            "--wav", str(wav_path),
            "-s", str(args.samplerate),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0 or not wav_path.exists():
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            sys.exit(f"sfizz_render failed (exit {result.returncode})")

        report = verify(wav_path, events)

    report.print_report()
    print("\n  NOTE: this verifies only the .sfz half of the kit -- "
          "DecentSampler's .dspreset format has no known headless renderer.")
    sys.exit(0 if report.passed else 1)


if __name__ == "__main__":
    main()
