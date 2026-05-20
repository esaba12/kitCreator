from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf


# Fallback freq-band split used when LarsNet isn't available
_DRUM_CLASS_FREQ_BANDS = {
    "kick":  (20,   200),
    "snare": (150,  800),
    "hihat": (6000, 20000),
    "perc":  (200,  6000),
}

MIN_ONSET_INTERVAL_S = 0.05
ONE_SHOT_MIN_MS = 50
ONE_SHOT_MAX_MS = 800
TAIL_DB = -55.0
MAX_ROUND_ROBINS = 4
MAX_VELOCITY_BUCKETS = 4


@dataclass
class OneShot:
    path: Path
    drum_class: str
    rr_index: int = 0
    vel_low: int = 0
    vel_high: int = 127


def slice_drum_stem(
    drum_wav: Path,
    out_dir: Path,
    debug: bool = False,
) -> list[OneShot]:
    """
    Slice a drum stem into per-class one-shot WAV files.

    Uses LarsNet sub-stem separation when weights are available;
    falls back to a frequency-band energy split otherwise.
    """
    from kitforge.separation.larsnet_runner import is_available, separate_drum_stem

    sample_dir = out_dir / "samples"
    sample_dir.mkdir(parents=True, exist_ok=True)

    if is_available():
        if debug:
            print("  Using LarsNet sub-stem separation")
        sub_stem_dir = out_dir / "_larsnet_stems"
        stem_wavs = separate_drum_stem(drum_wav, sub_stem_dir)
        return _slice_from_larsnet_stems(stem_wavs, sample_dir, debug=debug)
    else:
        if debug:
            print("  LarsNet not available — using frequency-band split fallback")
        return _slice_with_band_split(drum_wav, sample_dir, debug=debug)


def _slice_from_larsnet_stems(
    stem_wavs: dict[str, Path],
    sample_dir: Path,
    debug: bool = False,
) -> list[OneShot]:
    """Slice one-shots from LarsNet's clean per-class stem WAVs."""
    one_shots: list[OneShot] = []

    for drum_class, wav_path in stem_wavs.items():
        y, sr = librosa.load(str(wav_path), sr=None, mono=True)

        onsets = _detect_onsets(y, sr)
        if debug:
            print(f"  {drum_class}: {len(onsets)} onsets")

        slices = _slice_at_onsets(y, onsets, sr)

        y_stereo, _ = librosa.load(str(wav_path), sr=None, mono=False)
        is_stereo = y_stereo.ndim > 1 and y_stereo.shape[0] == 2

        bucketed = _assign_velocity_buckets(slices, drum_class, sr=sr)

        for vel_low, vel_high, rr_slices in bucketed:
            for rr_i, slc in enumerate(rr_slices):
                fname = sample_dir / f"{drum_class}_v{vel_low}_{rr_i + 1}.wav"
                if is_stereo:
                    sf.write(str(fname), np.stack([slc, slc]).T, sr)
                else:
                    sf.write(str(fname), slc, sr)
                one_shots.append(OneShot(
                    path=fname,
                    drum_class=drum_class,
                    rr_index=rr_i,
                    vel_low=vel_low,
                    vel_high=vel_high,
                ))

        if debug:
            print(f"    → {len(one_shots)} one-shots written for {drum_class}")

    return one_shots


def _slice_with_band_split(
    drum_wav: Path,
    sample_dir: Path,
    debug: bool = False,
) -> list[OneShot]:
    """Fallback: frequency-band energy split for onset detection, slices from full drum stem."""
    y, sr = librosa.load(str(drum_wav), sr=None, mono=False)
    y_mono = y.mean(axis=0) if y.ndim > 1 else y
    is_stereo = y.ndim > 1

    one_shots: list[OneShot] = []

    for drum_class, (lo, hi) in _DRUM_CLASS_FREQ_BANDS.items():
        band = _bandpass(y_mono, sr, lo, hi)
        onsets = _detect_onsets(band, sr)
        if debug:
            print(f"  {drum_class}: {len(onsets)} onsets")

        slices = _slice_at_onsets(y_mono, onsets, sr)
        bucketed = _assign_velocity_buckets(slices, drum_class, sr=sr)

        for vel_low, vel_high, rr_slices in bucketed:
            for rr_i, slc in enumerate(rr_slices):
                fname = sample_dir / f"{drum_class}_v{vel_low}_{rr_i + 1}.wav"
                if is_stereo:
                    sf.write(str(fname), np.stack([slc, slc]).T, sr)
                else:
                    sf.write(str(fname), slc, sr)
                one_shots.append(OneShot(
                    path=fname,
                    drum_class=drum_class,
                    rr_index=rr_i,
                    vel_low=vel_low,
                    vel_high=vel_high,
                ))

    return one_shots


def _assign_velocity_buckets(
    slices: list[tuple[float, np.ndarray]],
    drum_class: str,
    sr: int = 44100,
    n_buckets: int = MAX_VELOCITY_BUCKETS,
    rr_per_bucket: int = MAX_ROUND_ROBINS,
) -> list[tuple[int, int, list[np.ndarray]]]:
    """
    Sort (peak, audio) pairs by raw peak energy, divide into velocity layers,
    then pick rr_per_bucket timbrally-diverse round-robins per bucket via CLAP.

    Returns list of (vel_low, vel_high, [normalized_slices]) tuples.
    """
    if not slices:
        return []

    from kitforge.extract.cluster import pick_diverse_rr

    sorted_pairs = sorted(slices, key=lambda p: p[0])

    actual_buckets = min(n_buckets, max(1, len(sorted_pairs) // 2))
    bucket_size = len(sorted_pairs) / actual_buckets
    vel_step = 128 // actual_buckets

    result: list[tuple[int, int, list[np.ndarray]]] = []
    for b in range(actual_buckets):
        lo_i = int(b * bucket_size)
        hi_i = int((b + 1) * bucket_size)
        bucket = sorted_pairs[lo_i:hi_i]

        rr_audios = pick_diverse_rr(bucket, sr, n=rr_per_bucket)

        vel_low = b * vel_step
        vel_high = 127 if b == actual_buckets - 1 else (b + 1) * vel_step - 1
        result.append((vel_low, vel_high, rr_audios))

    return result


def _bandpass(y: np.ndarray, sr: int, lo: float, hi: float) -> np.ndarray:
    from scipy.signal import butter, sosfilt
    nyq = sr / 2.0
    lo_n = max(lo / nyq, 1e-4)
    hi_n = min(hi / nyq, 0.9999)
    sos = butter(4, [lo_n, hi_n], btype="band", output="sos")
    return sosfilt(sos, y).astype(np.float32)


def _detect_onsets(y: np.ndarray, sr: int) -> np.ndarray:
    onset_frames = librosa.onset.onset_detect(
        y=y, sr=sr, units="samples",
        hop_length=256, backtrack=True,
        pre_max=3, post_max=3, pre_avg=3, post_avg=5, delta=0.07, wait=10,
    )
    if len(onset_frames) == 0:
        return np.array([], dtype=int)

    min_gap = int(MIN_ONSET_INTERVAL_S * sr)
    kept = [int(onset_frames[0])]
    for o in onset_frames[1:]:
        if o - kept[-1] >= min_gap:
            kept.append(int(o))
    return np.array(kept, dtype=int)


def _slice_at_onsets(
    y: np.ndarray, onsets: np.ndarray, sr: int
) -> list[tuple[float, np.ndarray]]:
    """Return (raw_peak, normalized_slice) pairs. raw_peak drives velocity sorting."""
    if len(onsets) == 0:
        return []

    max_samples = int(ONE_SHOT_MAX_MS / 1000 * sr)
    min_samples = int(ONE_SHOT_MIN_MS / 1000 * sr)
    slices: list[tuple[float, np.ndarray]] = []

    for i, start in enumerate(onsets):
        end_hard = int(onsets[i + 1]) if i + 1 < len(onsets) else len(y)
        end = min(start + max_samples, end_hard)
        slc = y[start:end]

        if len(slc) < min_samples:
            continue

        slc = _trim_tail(slc, sr)
        if len(slc) < min_samples:
            continue

        peak = float(np.abs(slc).max())
        if peak > 0:
            slc = slc * (0.891 / peak)  # normalize to -1 dBFS

        slices.append((peak, slc.astype(np.float32)))

    return slices


def _trim_tail(slc: np.ndarray, sr: int) -> np.ndarray:
    threshold = 10 ** (TAIL_DB / 20.0)
    rms_hop = 256
    for i in range(len(slc) - rms_hop, 0, -rms_hop):
        if np.sqrt(np.mean(slc[i:i + rms_hop] ** 2)) > threshold:
            return slc[:i + rms_hop]
    return slc
