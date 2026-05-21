from __future__ import annotations

from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, indent, tostring

from kitforge.extract.slicer import OneShot
from kitforge.extract.pitched_slicer import PitchedShot


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


def write_pitched_dspreset(shots: list[PitchedShot], dspreset_path: Path) -> None:
    """Emit a DecentSampler .dspreset for a pitched instrument."""
    import numpy as np

    root = Element("DecentSampler", minVersion="1.0.0")

    ui = SubElement(root, "ui", width="812", height="375", bgMode="blank")
    SubElement(ui, "label", x="10", y="10", width="400", height="30",
               text="kitforge pitched kit", textSize="20", textColor="FFFFFFFF")

    # Compute median ADSR across all zones (DS ADSR is per-group, not per-sample)
    group_attrs: dict[str, str] = {}
    attacks  = [s.ampeg_attack  for s in shots if s.ampeg_attack  is not None]
    decays   = [s.ampeg_decay   for s in shots if s.ampeg_decay   is not None]
    sustains = [s.ampeg_sustain for s in shots if s.ampeg_sustain is not None]
    releases = [s.ampeg_release for s in shots if s.ampeg_release is not None]
    if attacks:
        group_attrs["attack"]  = f"{float(np.median(attacks)):.3f}"
    if decays:
        group_attrs["decay"]   = f"{float(np.median(decays)):.3f}"
    if sustains:
        # DS sustain is 0.0–1.0; SFZ is 0–100 %
        group_attrs["sustain"] = f"{float(np.median(sustains)) / 100.0:.3f}"
    if releases:
        group_attrs["release"] = f"{float(np.median(releases)):.3f}"

    groups_el = SubElement(root, "groups")
    group = SubElement(groups_el, "group", **group_attrs)

    for shot in sorted(shots, key=lambda s: s.lokey):
        rel_path = str(shot.path.relative_to(dspreset_path.parent))
        sample_attrs: dict[str, str] = {
            "path":     rel_path,
            "loNote":   str(shot.lokey),
            "hiNote":   str(shot.hikey),
            "rootNote": str(shot.midi_note),
            "loVel":    "0",
            "hiVel":    "127",
            "volume":   "1.0",
        }
        if shot.loop_start is not None:
            sample_attrs["loopStart"] = str(shot.loop_start)
            sample_attrs["loopEnd"]   = str(shot.loop_end)
            sample_attrs["loopCrossfade"] = "512"
        SubElement(group, "sample", **sample_attrs)

    indent(root, space="  ")
    xml_bytes = tostring(root, encoding="unicode", xml_declaration=False)
    dspreset_path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes + "\n")
