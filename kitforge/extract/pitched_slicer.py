"""Slice a monophonic bass/lead stem into per-MIDI-note samples with pitch-fill."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


# f0 tracking params for bass (E1=41Hz – G4=392Hz)
_BASS_FMIN = 35.0
_BASS_FMAX = 420.0
_HOP_LENGTH = 512

CONFIDENCE_THRESHOLD = 0.55       # periodicity below this → unvoiced
PITCH_STABILITY_CENTS = 60.0      # ±60 cents (±0.5 st) to keep frame in same note
MIN_NOTE_DURATION_S = 0.06
MAX_NOTE_DURATION_S = 4.0
NORMALIZE_DBFS = -1.0
MAX_SHIFT_SEMITONES = 6           # beyond this, pre-shift with Rubber Band


@dataclass
class PitchedShot:
    path: Path
    midi_note: int   # the actual MIDI note of the audio
    lokey: int       # SFZ/DS zone low boundary
    hikey: int       # SFZ/DS zone high boundary


_CREPE_SR = 16000  # torchcrepe's native rate — load at this to avoid double-buffering
_TRACK_MAX_S = 90.0  # cap f0 tracking to first N seconds — enough to find all pitches


def slice_bass_stem(
    bass_wav: Path,
    out_dir: Path,
    note_range: tuple[int, int] = (24, 67),  # C1–G4
    debug: bool = False,
) -> list[PitchedShot]:
    """Extract per-note samples from a bass stem, fill the target MIDI range."""
    from kitforge.transcribe.crepe_mono import track_f0
    from kitforge.pitchshift.rubberband_wrapper import pitch_shift

    # Load at native SR for high-quality sample slicing
    y, sr = librosa.load(str(bass_wav), sr=None, mono=True)

    if debug:
        print(f"  bass: loaded {len(y)/sr:.1f}s @ {sr}Hz")

    # Load at 16kHz, capped, for f0 tracking — avoids OOM on long songs
    track_samples = int(_TRACK_MAX_S * _CREPE_SR)
    y_track, _ = librosa.load(str(bass_wav), sr=_CREPE_SR, mono=True)
    y_track = y_track[:track_samples]
    if debug:
        print(f"  bass: tracking f0 on {len(y_track)/_CREPE_SR:.1f}s")

    times, f0, periodicity = track_f0(
        y_track, _CREPE_SR, hop_length=_HOP_LENGTH, fmin=_BASS_FMIN, fmax=_BASS_FMAX
    )

    del y_track  # free 16kHz buffer before heavy slicing work

    note_events = _segment_notes(times, f0, periodicity, sr)
    if debug:
        print(f"  bass: {len(note_events)} note events detected")

    # Best sample per MIDI pitch
    real_samples: dict[int, np.ndarray] = _collect_real_samples(y, sr, note_events, debug)
    if debug:
        print(f"  bass: {len(real_samples)} unique pitches: {sorted(real_samples)}")

    if not real_samples:
        return []

    sample_dir = out_dir / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    lo, hi = note_range
    shots = _fill_range(real_samples, lo, hi, sample_dir, sr, pitch_shift, debug)
    return shots


def slice_pitched_stem(
    stem_wav: Path,
    note_events: list[tuple[float, float, int, float]],  # (start_s, end_s, midi, amplitude)
    out_dir: Path,
    note_range: tuple[int, int] = (36, 84),  # C2–C6
    debug: bool = False,
) -> list[PitchedShot]:
    """
    Slice a polyphonic pitched stem using pre-computed note events (e.g. from Basic Pitch).
    Used for guitar, piano, synth — anything that isn't bass.
    """
    from kitforge.pitchshift.rubberband_wrapper import pitch_shift

    y, sr = librosa.load(str(stem_wav), sr=None, mono=True)

    if debug:
        print(f"  pitched: loaded {len(y)/sr:.1f}s @ {sr}Hz, {len(note_events)} note events")

    # Strip amplitude — _collect_real_samples only needs (start, end, midi)
    events_triples = [(s, e, n) for s, e, n, _ in note_events]
    real_samples = _collect_real_samples(y, sr, events_triples, debug)

    if debug:
        print(f"  pitched: {len(real_samples)} unique pitches: {sorted(real_samples)}")

    if not real_samples:
        return []

    sample_dir = out_dir / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    lo, hi = note_range
    return _fill_range(real_samples, lo, hi, sample_dir, sr, pitch_shift, debug)


# ── internal helpers ─────────────────────────────────────────────────────────

def _hz_to_midi(f0: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        midi = np.where(f0 > 0, 69.0 + 12.0 * np.log2(f0 / 440.0), np.nan)
    return midi


def _segment_notes(
    times: np.ndarray,
    f0: np.ndarray,
    periodicity: np.ndarray,
    sr: int,
) -> list[tuple[float, float, int]]:
    """Return list of (start_s, end_s, midi_note) for voiced segments."""
    midi_float = _hz_to_midi(f0)
    hop_s = _HOP_LENGTH / sr

    events: list[tuple[float, float, int]] = []
    seg_start: int | None = None
    seg_pitches: list[float] = []

    for i, (conf, mf) in enumerate(zip(periodicity, midi_float)):
        voiced = conf >= CONFIDENCE_THRESHOLD and not np.isnan(mf)

        if voiced:
            if seg_start is None:
                seg_start = i
                seg_pitches = [mf]
            else:
                # Check stability relative to current segment median
                if abs(mf - float(np.median(seg_pitches))) * 100 <= PITCH_STABILITY_CENTS:
                    seg_pitches.append(mf)
                else:
                    # Flush current segment, start new
                    _maybe_add(events, seg_start, i, seg_pitches, hop_s)
                    seg_start = i
                    seg_pitches = [mf]
        else:
            if seg_start is not None:
                _maybe_add(events, seg_start, i, seg_pitches, hop_s)
                seg_start = None
                seg_pitches = []

    if seg_start is not None:
        _maybe_add(events, seg_start, len(times), seg_pitches, hop_s)

    return events


def _maybe_add(
    events: list[tuple[float, float, int]],
    start_i: int,
    end_i: int,
    pitches: list[float],
    hop_s: float,
) -> None:
    dur = (end_i - start_i) * hop_s
    if dur < MIN_NOTE_DURATION_S:
        return
    midi_note = int(round(float(np.median(pitches))))
    events.append((start_i * hop_s, end_i * hop_s, midi_note))


def _collect_real_samples(
    y: np.ndarray,
    sr: int,
    note_events: list[tuple[float, float, int]],
    debug: bool,
) -> dict[int, np.ndarray]:
    """Pick the longest occurrence per MIDI note as the canonical sample."""
    best: dict[int, tuple[float, np.ndarray]] = {}  # midi → (duration, audio)

    for start_s, end_s, midi_note in note_events:
        dur = end_s - start_s
        if midi_note in best and best[midi_note][0] >= dur:
            continue
        start_i = int(start_s * sr)
        end_i = min(int(end_s * sr), len(y))
        slc = y[start_i:end_i]
        slc = slc[:int(MAX_NOTE_DURATION_S * sr)]
        peak = float(np.abs(slc).max())
        if peak == 0:
            continue
        target = 10 ** (NORMALIZE_DBFS / 20.0)
        slc = (slc * (target / peak)).astype(np.float32)
        best[midi_note] = (dur, slc)

    return {note: audio for note, (_, audio) in best.items()}


def _fill_range(
    real_samples: dict[int, np.ndarray],
    lo: int,
    hi: int,
    sample_dir: Path,
    sr: int,
    pitch_shift_fn: object,
    debug: bool,
) -> list[PitchedShot]:
    """
    For each semitone in [lo, hi], find the nearest real sample.
    Pre-shift with Rubber Band if gap > MAX_SHIFT_SEMITONES; otherwise
    let the sampler do it (wider zone).
    """
    real_notes = sorted(real_samples)
    shots: list[PitchedShot] = []

    # Zone boundaries: midpoint between adjacent real samples
    zone_splits = _zone_splits(real_notes, lo, hi)

    for midi_note, (zone_lo, zone_hi) in zone_splits.items():
        nearest = _nearest(midi_note, real_notes)
        shift = midi_note - nearest
        audio = real_samples[nearest]

        if abs(shift) > MAX_SHIFT_SEMITONES:
            # Pre-generate the shifted file
            audio = pitch_shift_fn(audio, sr, float(shift))
            src_note = midi_note
        else:
            src_note = nearest  # sampler handles the small shift

        note_name = librosa.midi_to_note(midi_note).replace("#", "s").replace("♯", "s").replace(" ", "")
        fname = sample_dir / f"bass_{note_name}_midi{midi_note}.wav"
        sf.write(str(fname), audio, sr, subtype="PCM_24")

        shots.append(PitchedShot(
            path=fname,
            midi_note=src_note,
            lokey=zone_lo,
            hikey=zone_hi,
        ))

        if debug:
            arrow = f"shifted {shift:+d}st from {nearest}" if shift != 0 else "real"
            print(f"  {note_name} (midi {midi_note}): {arrow}, zone [{zone_lo},{zone_hi}]")

    return shots


def _zone_splits(real_notes: list[int], lo: int, hi: int) -> dict[int, tuple[int, int]]:
    """Return {anchor_midi: (lokey, hikey)} covering [lo, hi] with Voronoi splits."""
    # Only keep real notes within the usable range (allow ±MAX_SHIFT_SEMITONES outside)
    anchors = [n for n in real_notes if lo - MAX_SHIFT_SEMITONES <= n <= hi + MAX_SHIFT_SEMITONES]
    if not anchors:
        return {}

    zones: dict[int, tuple[int, int]] = {}
    for i, anchor in enumerate(anchors):
        zone_lo = lo if i == 0 else (anchors[i - 1] + anchor) // 2 + 1
        zone_hi = hi if i == len(anchors) - 1 else (anchor + anchors[i + 1]) // 2
        # Clip to target range
        zone_lo = max(zone_lo, lo)
        zone_hi = min(zone_hi, hi)
        if zone_lo <= zone_hi:
            zones[anchor] = (zone_lo, zone_hi)

    return zones


def _nearest(midi: int, candidates: list[int]) -> int:
    return min(candidates, key=lambda n: abs(n - midi))
