import numpy as np

import kitforge.extract.cluster as cluster
from kitforge.extract import slicer

SR = 44100


def test_bandpass_attenuates_out_of_band_energy():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    low = np.sin(2 * np.pi * 100.0 * t)
    high = np.sin(2 * np.pi * 10000.0 * t)
    mixed = (low + high).astype(np.float32)

    filtered = slicer._bandpass(mixed, SR, 6000, 20000)

    low_only_energy = np.sqrt(np.mean(slicer._bandpass(low.astype(np.float32), SR, 6000, 20000) ** 2))
    high_only_energy = np.sqrt(np.mean(slicer._bandpass(high.astype(np.float32), SR, 6000, 20000) ** 2))
    assert high_only_energy > low_only_energy * 5


def test_detect_onsets_finds_impulses_and_merges_close_hits():
    y = np.zeros(SR, dtype=np.float32)
    for sample in (1000, 1200, 20000, 40000):  # 1000/1200 closer than MIN_ONSET_INTERVAL_S
        y[sample] = 1.0
    onsets = slicer._detect_onsets(y, SR)
    assert len(onsets) <= 3  # 1000 and 1200 should collapse to one
    assert len(onsets) >= 2


def test_trim_tail_cuts_silence_after_decay():
    sr = SR
    audio = np.zeros(sr, dtype=np.float32)
    audio[: sr // 4] = 0.9  # loud first quarter, silent rest
    trimmed = slicer._trim_tail(audio, sr)
    assert len(trimmed) < len(audio)
    assert len(trimmed) >= sr // 4


def test_slice_at_onsets_normalizes_and_bounds_length():
    y = np.zeros(SR, dtype=np.float32)
    y[1000:1010] = 0.5
    y[20000:20010] = 0.1
    onsets = np.array([1000, 20000])

    slices = slicer._slice_at_onsets(y, onsets, SR)
    assert len(slices) == 2
    for peak, slc in slices:
        assert peak > 0
        assert len(slc) <= int(slicer.ONE_SHOT_MAX_MS / 1000 * SR)
        assert np.abs(slc).max() <= 0.891 + 1e-6


def test_assign_velocity_buckets_splits_by_energy_and_respects_bucket_count(monkeypatch):
    monkeypatch.setattr(cluster, "pick_diverse_rr", lambda clips, sr, n: [a for _, a in clips][:n])

    slices = [(float(i), np.full(4, i, dtype=np.float32)) for i in range(8)]
    buckets = slicer._assign_velocity_buckets(slices, "snare", sr=SR, n_buckets=4, rr_per_bucket=2)

    assert len(buckets) == 4
    vel_los = [b[0] for b in buckets]
    assert vel_los == sorted(vel_los)
    assert buckets[-1][1] == 127  # top bucket always reaches vel 127


def test_assign_velocity_buckets_empty_input_returns_empty():
    assert slicer._assign_velocity_buckets([], "kick") == []
