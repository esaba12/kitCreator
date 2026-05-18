from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent, tostring

from kitforge.extract.slicer import OneShot


_DRUM_MIDI = {
    "kick":    36,
    "snare":   38,
    "hihat":   42,
    "toms":    47,
    "cymbals": 48,
    "perc":    47,
}


def write_drum_dspreset(one_shots: list[OneShot], dspreset_path: Path) -> None:
    """Emit a DecentSampler .dspreset drum kit."""
    root = Element("DecentSampler", minVersion="1.0.0")

    ui = SubElement(root, "ui", width="812", height="375", bgMode="blank")
    SubElement(ui, "label", x="10", y="10", width="400", height="30",
               text="kitforge drum kit", textSize="20", textColor="FFFFFFFF")

    groups_el = SubElement(root, "groups")

    by_class: dict[str, list[OneShot]] = {}
    for shot in one_shots:
        by_class.setdefault(shot.drum_class, []).append(shot)

    for drum_class, shots in by_class.items():
        midi_note = _DRUM_MIDI.get(drum_class, 48)
        is_hihat = drum_class == "hihat"

        # One DS group per velocity layer (DS seqMode is per-group)
        by_vel: dict[tuple[int, int], list[OneShot]] = {}
        for shot in shots:
            key = (shot.vel_low, shot.vel_high)
            by_vel.setdefault(key, []).append(shot)

        for (vel_low, vel_high), vel_shots in sorted(by_vel.items()):
            rr_count = len(vel_shots)
            group_attrs: dict[str, str] = {
                "seqMode": "round_robin" if rr_count > 1 else "always",
            }
            if is_hihat:
                group_attrs["silencedByTags"] = "hihat"
                group_attrs["tags"] = "hihat"

            group = SubElement(groups_el, "group", **group_attrs)

            for shot in vel_shots:
                rel_path = str(shot.path.relative_to(dspreset_path.parent))
                SubElement(group, "sample", **{
                    "path": rel_path,
                    "loNote": str(midi_note),
                    "hiNote": str(midi_note),
                    "rootNote": str(midi_note),
                    "loVel": str(vel_low),
                    "hiVel": str(vel_high),
                    "volume": "1.0",
                    "seqPosition": str(shot.rr_index + 1),
                })

    indent(root, space="  ")
    xml_bytes = tostring(root, encoding="unicode", xml_declaration=False)
    dspreset_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes + "\n")
