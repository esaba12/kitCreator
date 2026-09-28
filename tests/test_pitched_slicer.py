import numpy as np

import kitforge.extract.cluster as cluster
from kitforge.extract.pitched_slicer import (
    _collect_real_samples,
    _hz_to_midi,
    _nearest,
    _segment_notes,
    _zone_splits,
)

SR = 16000
HOP_S = 512 / SR


def test_hz_to_midi_known_reference_pitch():
    midi = _hz_to_midi(np.array([440.0]))
    assert round(float(midi[0])) == 69


def test_hz_to_midi_unvoiced_frame_is_nan():
    midi = _hz_to_midi(np.array([0.0]))
    assert np.isnan(midi[0])


def _voiced_run(n_frames: int, freq: float, conf: float = 0.9):
    return np.full(n_frames, freq), np.full(n_frames, conf)


def test_segment_notes_produces_one_event_for_stable_pitch():
    f0, periodicity = _voiced_run(30, 261.63)  # ~C4, well above MIN_NOTE_DURATION_S
    times = np.arange(30) * HOP_S
    events = _segment_notes(times, f0, periodicity, SR)
    assert len(events) == 1
    start_s, end_s, midi_note = events[0]
    assert midi_note == 60
    assert end_s - start_s > 0.06


def test_segment_notes_drops_blips_shorter_than_min_duration():
    f0, periodicity = _voiced_run(1, 261.63)  # 1 frame (32ms) << MIN_NOTE_DURATION_S (60ms)
    times = np.arange(1) * HOP_S
    events = _segment_notes(times, f0, periodicity, SR)
    assert events == []


def test_segment_notes_splits_on_pitch_jump():
    f0_low, conf_low = _voiced_run(20, 261.63)   # C4
    f0_high, conf_high = _voiced_run(20, 523.25)  # C5, unrelated pitch
    f0 = np.concatenate([f0_low, f0_high])
    periodicity = np.concatenate([conf_low, conf_high])
    times = np.arange(40) * HOP_S

    events = _segment_notes(times, f0, periodicity, SR)
    assert len(events) == 2
    assert events[0][2] == 60
    assert events[1][2] == 72


def test_segment_notes_unvoiced_gap_breaks_segment():
    f0_a, conf_a = _voiced_run(20, 261.63)
    f0_gap, conf_gap = np.zeros(10), np.zeros(10)
    f0_b, conf_b = _voiced_run(20, 261.63)
    f0 = np.concatenate([f0_a, f0_gap, f0_b])
    periodicity = np.concatenate([conf_a, conf_gap, conf_b])
    times = np.arange(50) * HOP_S

    events = _segment_notes(times, f0, periodicity, SR)
    assert len(events) == 2


def test_nearest_picks_closest_candidate():
    assert _nearest(44, [30, 40, 50]) == 40
    assert _nearest(45, [30, 40, 50]) == 40  # tie broken toward first-min (40 before 50)


def test_zone_splits_covers_full_range_with_midpoints():
    zones = _zone_splits([40, 50, 60], lo=36, hi=64)
    assert set(zones) == {40, 50, 60}
    assert zones[40][0] == 36
    assert zones[60][1] == 64
    # adjacent zones should be contiguous, no gaps or overlaps
    assert zones[40][1] + 1 == zones[50][0]
    assert zones[50][1] + 1 == zones[60][0]


def test_zone_splits_empty_when_no_anchors_in_range():
    assert _zone_splits([], lo=36, hi=64) == {}


def test_collect_real_samples_picks_medoid_per_note(monkeypatch):
    monkeypatch.setattr(cluster, "pick_medoid", lambda occurrences, sr: occurrences[0][1])

    sr = 44100
    y = np.zeros(sr * 2, dtype=np.float32)
    y[1000:5000] = 0.5
    y[10000:14000] = 0.3

    note_events = [(1000 / sr, 5000 / sr, 60), (10000 / sr, 14000 / sr, 60)]
    result = _collect_real_samples(y, sr, note_events, debug=False)

    assert list(result.keys()) == [60]
    assert np.abs(result[60]).max() > 0
