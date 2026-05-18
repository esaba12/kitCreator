from __future__ import annotations

from pathlib import Path

from kitforge.extract.slicer import OneShot
from kitforge.extract.pitched_slicer import PitchedShot


# MIDI note assignments per drum class (GM-ish layout)
_DRUM_MIDI = {
    "kick":    36,
    "snare":   38,
    "hihat":   42,
    "toms":    47,
    "cymbals": 48,
    "perc":    47,
}

# Hi-hat choke group
_HIHAT_GROUP = 1

_HEADER = """\
// kitforge drum kit — SFZ format
// sfzformat.com spec

<global>
ampeg_release=0.05
"""


def write_drum_sfz(one_shots: list[OneShot], sfz_path: Path) -> None:
    """Emit a SFZ drum kit from a list of one-shots."""
    lines = [_HEADER]

    by_class: dict[str, list[OneShot]] = {}
    for shot in one_shots:
        by_class.setdefault(shot.drum_class, []).append(shot)

    for drum_class, shots in by_class.items():
        midi_note = _DRUM_MIDI.get(drum_class, 48)
        is_hihat = drum_class == "hihat"

        # Group by velocity layer so seq_length is per-layer, not global
        by_vel: dict[tuple[int, int], list[OneShot]] = {}
        for shot in shots:
            key = (shot.vel_low, shot.vel_high)
            by_vel.setdefault(key, []).append(shot)

        lines.append(f"\n// {drum_class}")
        group_line = f"<group> lokey={midi_note} hikey={midi_note} pitch_keycenter={midi_note}"
        if is_hihat:
            group_line += f" group={_HIHAT_GROUP} off_by={_HIHAT_GROUP} off_mode=fast"
        lines.append(group_line)

        for (vel_low, vel_high), vel_shots in sorted(by_vel.items()):
            rr_count = len(vel_shots)
            for shot in vel_shots:
                rel_path = shot.path.relative_to(sfz_path.parent)
                region = f"<region> sample={rel_path} lovel={vel_low} hivel={vel_high}"
                if rr_count > 1:
                    region += f" seq_position={shot.rr_index + 1} seq_length={rr_count}"
                lines.append(region)

    sfz_path.write_text("\n".join(lines) + "\n")


def write_pitched_sfz(shots: list[PitchedShot], sfz_path: Path) -> None:
    """Emit a SFZ pitched instrument (bass, etc.) — one zone per note."""
    lines = [
        "// kitforge pitched kit — SFZ format\n"
        "<global>\nampeg_release=0.3\n",
        "<group>",
    ]
    for shot in sorted(shots, key=lambda s: s.lokey):
        rel_path = shot.path.relative_to(sfz_path.parent)
        lines.append(
            f"<region> sample={rel_path}"
            f" lokey={shot.lokey} hikey={shot.hikey}"
            f" pitch_keycenter={shot.midi_note}"
        )
    sfz_path.write_text("\n".join(lines) + "\n")
