"""Verify a sfizz_render output WAV actually contains audio at every expected note-on."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from tests.acceptance.generate_test_midi import NoteEvent

ATTACK_SKIP_S = 0.015
ANALYSIS_WINDOW_S = 0.25
NOISE_FLOOR_MARGIN = 5.0
ABSOLUTE_FLOOR = 1e-4
DURATION_FLOOR_S = 0.3
DURATION_CEILING_S = 5.0
VELOCITY_TOLERANCE = 0.8  # high-vel hit's RMS must be >= this fraction of low-vel hit's


@dataclass
class NoteResult:
    event: NoteEvent
    window_rms: float
    passed: bool


@dataclass
class VerificationReport:
    duration_s: float
    duration_ok: bool
    global_rms: float
    peak: float
    has_nan_or_inf: bool
    global_ok: bool
    noise_floor_rms: float
    note_results: list[NoteResult]
    velocity_warnings: list[str]

    @property
    def passed(self) -> bool:
        return (
            self.duration_ok
            and self.global_ok
            and all(r.passed for r in self.note_results)
        )

    def print_report(self) -> None:
        print(f"  duration: {self.duration_s:.2f}s ({'ok' if self.duration_ok else 'FAIL'})")
        print(f"  global RMS: {self.global_rms:.5f}, peak: {self.peak:.3f}, "
              f"NaN/Inf: {self.has_nan_or_inf} ({'ok' if self.global_ok else 'FAIL'})")
        print(f"  noise floor RMS: {self.noise_floor_rms:.6f}")
        print(f"  {'note':>6} {'label':<16} {'time':>6} {'rms':>10} {'status':>6}")
        for r in self.note_results:
            status = "ok" if r.passed else "FAIL"
            print(f"  {r.event.midi_note:>6} {r.event.label:<16} "
                  f"{r.event.start:>6.2f} {r.window_rms:>10.6f} {status:>6}")
        for w in self.velocity_warnings:
            print(f"  [warn] {w}")
        n_pass = sum(r.passed for r in self.note_results)
        print(f"  summary: {n_pass}/{len(self.note_results)} notes sounded, "
              f"overall {'PASS' if self.passed else 'FAIL'}")


def _window_rms(mono: np.ndarray, sr: int, t0: float, t1: float) -> float:
    i0 = max(0, int(t0 * sr))
    i1 = min(len(mono), int(t1 * sr))
    if i1 <= i0:
        return 0.0
    window = mono[i0:i1]
    return float(np.sqrt(np.mean(window ** 2)))


def _check_velocity_sensitivity(events: list[NoteEvent], results: list[NoteResult]) -> list[str]:
    by_note: dict[int, list[NoteResult]] = {}
    for r in results:
        by_note.setdefault(r.event.midi_note, []).append(r)

    warnings: list[str] = []
    for note, note_results in by_note.items():
        if len(note_results) != 2:
            continue
        lo, hi = note_results  # chronological: lo-velocity hit scheduled first
        if hi.window_rms < lo.window_rms * VELOCITY_TOLERANCE:
            warnings.append(
                f"note {note}: high-velocity hit ({hi.window_rms:.6f} RMS) quieter than "
                f"low-velocity hit ({lo.window_rms:.6f} RMS) -- check velocity bucket assignment"
            )
    return warnings


def verify(wav_path: Path, events: list[NoteEvent]) -> VerificationReport:
    data, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
    mono = data.mean(axis=1) if data.size else data.reshape(-1)

    duration_s = len(mono) / sr if sr else 0.0
    last_on = max((e.start for e in events), default=0.0)
    duration_ok = (last_on + DURATION_FLOOR_S) <= duration_s <= (last_on + DURATION_CEILING_S)

    peak = float(np.abs(mono).max()) if len(mono) else 0.0
    global_rms = float(np.sqrt(np.mean(mono ** 2))) if len(mono) else 0.0
    has_nan_or_inf = bool(np.isnan(mono).any() or np.isinf(mono).any())
    global_ok = global_rms > ABSOLUTE_FLOOR and peak <= 1.0 + 1e-3 and not has_nan_or_inf

    first_on = min((e.start for e in events), default=0.0)
    noise_floor_rms = _window_rms(mono, sr, 0.0, max(0.0, first_on - 0.05))
    threshold = max(noise_floor_rms * NOISE_FLOOR_MARGIN, ABSOLUTE_FLOOR)

    note_results = []
    for e in events:
        rms = _window_rms(mono, sr, e.start + ATTACK_SKIP_S, e.start + ANALYSIS_WINDOW_S)
        note_results.append(NoteResult(e, rms, rms > threshold))

    velocity_warnings = _check_velocity_sensitivity(events, note_results)

    return VerificationReport(
        duration_s=duration_s,
        duration_ok=duration_ok,
        global_rms=global_rms,
        peak=peak,
        has_nan_or_inf=has_nan_or_inf,
        global_ok=global_ok,
        noise_floor_rms=noise_floor_rms,
        note_results=note_results,
        velocity_warnings=velocity_warnings,
    )
