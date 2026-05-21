"""Export kit samples to Roland MC-101 SD card structure."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

from kitforge.extract.slicer import OneShot
from kitforge.extract.pitched_slicer import PitchedShot

# Roland MC-101 pad assignments (1-indexed, displayed on device)
_PAD_MAP = {
    "kick":    1,
    "snare":   2,
    "hihat":   3,
    "toms":    5,
    "cymbals": 9,
    "perc":    13,
}

_SAMPLE_ROOT = Path("ROLAND") / "GROOVEBOX" / "SAMPLE"


def export_drums(shots: list[OneShot], kit_name: str, sd_root: Path) -> Path:
    """Copy drum WAVs (as PCM_16) to SD card and write SETUP.txt."""
    folder = sd_root / _SAMPLE_ROOT / f"{kit_name}_drums"
    folder.mkdir(parents=True, exist_ok=True)

    by_class: dict[str, list[OneShot]] = {}
    for shot in shots:
        by_class.setdefault(shot.drum_class, []).append(shot)

    copied: list[str] = []
    for drum_class, class_shots in sorted(by_class.items()):
        for shot in class_shots:
            dst = folder / shot.path.name
            _copy_wav_pcm16(shot.path, dst)
            copied.append(shot.path.name)

    setup_lines = [
        f"MC-101 Drum Kit — {kit_name}",
        "",
        "PAD ASSIGNMENTS",
        "───────────────",
    ]
    for drum_class, pad in sorted(_PAD_MAP.items(), key=lambda kv: kv[1]):
        if drum_class in by_class:
            n = len(by_class[drum_class])
            vel_note = f"  ({n} velocity layer{'s' if n > 1 else ''})"
            setup_lines.append(f"  Pad {pad:2d}  {drum_class:<10}{vel_note}")

    setup_lines += [
        "",
        "LOADING STEPS",
        "─────────────",
        "1. Eject SD card safely, insert into MC-101.",
        "2. On MC-101: MENU → Sample Manager → Sample Load.",
        f"3. Navigate to SAMPLE / {kit_name}_drums.",
        "4. Load each file onto its pad (see assignments above).",
        "5. To use velocity layers: load v0 → v1 → v2 → v3 to the same pad;",
        "   the MC-101 will stack them as velocity layers automatically.",
        "",
        "Files:",
    ]
    for name in copied:
        setup_lines.append(f"  {name}")

    (folder / "SETUP.txt").write_text("\n".join(setup_lines) + "\n")
    return folder


def export_pitched(shots: list[PitchedShot], instrument: str, kit_name: str, sd_root: Path) -> Path:
    """Copy the root-pitch sample to SD card and write SETUP.txt.

    The MC-101 Tone track transposes a single sample chromatically, so we
    export the sample closest to the median MIDI note in the kit.
    """
    folder = sd_root / _SAMPLE_ROOT / f"{kit_name}_{instrument.replace(' ', '_')}"
    folder.mkdir(parents=True, exist_ok=True)

    root_shot = _pick_root(shots)
    dst_name = f"{instrument.replace(' ', '_')}_root.wav"
    dst = folder / dst_name

    # Pitched WAVs are already PCM_24 — copy directly
    import shutil
    shutil.copy2(root_shot.path, dst)

    root_note_name = _midi_to_note(root_shot.midi_note)

    setup_lines = [
        f"MC-101 Tone Sample — {kit_name} ({instrument})",
        "",
        "LOADING STEPS",
        "─────────────",
        "1. Eject SD card safely, insert into MC-101.",
        "2. On MC-101: MENU → Sample Manager → Sample Load.",
        f"3. Navigate to SAMPLE / {folder.name}.",
        f"4. Load  {dst_name}  onto a Tone track.",
        f"5. Set the sample's Root Key to  {root_note_name}  (MIDI {root_shot.midi_note}).",
        "   The MC-101 will transpose it chromatically across the keyboard.",
        "",
        f"Root sample: {dst_name}",
        f"Root key:    {root_note_name} (MIDI {root_shot.midi_note})",
        f"Kit range:   MIDI {min(s.lokey for s in shots)}–{max(s.hikey for s in shots)}",
    ]

    (folder / "SETUP.txt").write_text("\n".join(setup_lines) + "\n")
    return folder


# ── helpers ──────────────────────────────────────────────────────────────────

def _copy_wav_pcm16(src: Path, dst: Path) -> None:
    """Re-encode a WAV as PCM_16 (MC-101 requirement)."""
    audio, sr = sf.read(str(src), always_2d=False)
    # Clip to [-1, 1] before int16 conversion to avoid overflow
    audio = np.clip(audio, -1.0, 1.0)
    sf.write(str(dst), audio, sr, subtype="PCM_16")


def _pick_root(shots: list[PitchedShot]) -> PitchedShot:
    """Return the shot whose midi_note is closest to the median."""
    notes = [s.midi_note for s in shots]
    median_note = float(np.median(notes))
    return min(shots, key=lambda s: abs(s.midi_note - median_note))


def _midi_to_note(midi: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (midi // 12) - 1
    return f"{names[midi % 12]}{octave}"
