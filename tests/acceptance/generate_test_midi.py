"""Build a test MIDI file that exercises every note actually present in a built kit.sfz.

Never hardcodes drum-class MIDI notes or a pitched instrument's key range --
everything is discovered by parsing the kit's own SFZ regions (sfz_parser.py),
so this stays correct even if sfz_writer.py's note assignments change.
"""
from __future__ import annotations

from dataclasses import dataclass

import pretty_midi

from tests.acceptance.sfz_parser import Region

HIT_SPACING_S = 1.0
HIT_DURATION_S = 0.3
CHOKE_GAP_S = 0.4

PITCHED_STRIDE_SEMITONES = 5
PITCHED_SPACING_S = 0.8
PITCHED_DURATION_S = 0.4
PITCHED_VELOCITY = 100


@dataclass
class NoteEvent:
    midi_note: int
    velocity: int
    start: float
    duration: float
    label: str


def _bucket_velocity(lovel: int, hivel: int) -> int:
    return max(1, min(127, (lovel + hivel) // 2))


def build_drum_midi(regions: list[Region]) -> tuple[pretty_midi.PrettyMIDI, list[NoteEvent]]:
    """One low-velocity + one high-velocity hit per distinct drum note.

    Notes carrying a choke group (any region opcode `group=`) are scheduled as
    their own isolated back-to-back pair after the main sequence, so a choke
    cutoff can't be misread as a different, unrelated note going silent.
    """
    by_note: dict[int, set[tuple[int, int]]] = {}
    choked_notes: set[int] = set()

    for r in regions:
        note = r.int("pitch_keycenter")
        if note is None:
            note = r.int("lokey")
        if note is None:
            continue
        lovel = r.int("lovel", 0)
        hivel = r.int("hivel", 127)
        by_note.setdefault(note, set()).add((lovel, hivel))
        if "group" in r.opcodes:
            choked_notes.add(note)

    events: list[NoteEvent] = []
    t = 0.0

    def _emit(note: int) -> None:
        nonlocal t
        buckets = sorted(by_note[note])
        lo_bucket, hi_bucket = buckets[0], buckets[-1]
        for tag, bucket in (("lo", lo_bucket), ("hi", hi_bucket)):
            vel = _bucket_velocity(*bucket)
            events.append(NoteEvent(note, vel, t, HIT_DURATION_S, f"note{note}_v{tag}{vel}"))
            t += HIT_SPACING_S

    for note in sorted(n for n in by_note if n not in choked_notes):
        _emit(note)

    for note in sorted(choked_notes):
        buckets = sorted(by_note[note])
        lo_vel = _bucket_velocity(*buckets[0])
        hi_vel = _bucket_velocity(*buckets[-1])
        events.append(NoteEvent(note, lo_vel, t, HIT_DURATION_S, f"choke{note}_lo{lo_vel}"))
        t += CHOKE_GAP_S
        events.append(NoteEvent(note, hi_vel, t, HIT_DURATION_S, f"choke{note}_hi{hi_vel}"))
        t += HIT_SPACING_S

    pm = _events_to_midi(events, is_drum=True)
    return pm, events


def build_pitched_midi(regions: list[Region]) -> tuple[pretty_midi.PrettyMIDI, list[NoteEvent]]:
    """One hit every PITCHED_STRIDE_SEMITONES across the kit's real lokey-hikey range."""
    lokeys = [v for r in regions if (v := r.int("lokey")) is not None]
    hikeys = [v for r in regions if (v := r.int("hikey")) is not None]
    if not lokeys or not hikeys:
        raise ValueError("No lokey/hikey opcodes found in SFZ regions")

    lo, hi = min(lokeys), max(hikeys)
    notes = list(range(lo, hi + 1, PITCHED_STRIDE_SEMITONES))
    if notes[-1] != hi:
        notes.append(hi)

    events: list[NoteEvent] = []
    t = 0.0
    for note in notes:
        events.append(NoteEvent(note, PITCHED_VELOCITY, t, PITCHED_DURATION_S, f"note{note}"))
        t += PITCHED_SPACING_S

    pm = _events_to_midi(events, is_drum=False)
    return pm, events


def _events_to_midi(events: list[NoteEvent], is_drum: bool) -> pretty_midi.PrettyMIDI:
    pm = pretty_midi.PrettyMIDI()
    inst = pretty_midi.Instrument(program=0, is_drum=is_drum)
    for e in events:
        inst.notes.append(pretty_midi.Note(
            velocity=e.velocity, pitch=e.midi_note,
            start=e.start, end=e.start + e.duration,
        ))
    pm.instruments.append(inst)
    return pm
