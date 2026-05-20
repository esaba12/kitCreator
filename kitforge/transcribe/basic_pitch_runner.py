"""Polyphonic note transcription via Spotify Basic Pitch (CoreML model on Mac)."""
from __future__ import annotations

import io
import logging
import os
import sys
import warnings
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def _silence():
    """Suppress stdout/stderr and all logging during Basic Pitch inference."""
    devnull = open(os.devnull, "w")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = devnull, devnull
    logging.disable(logging.CRITICAL)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            yield
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        devnull.close()
        logging.disable(logging.NOTSET)


def transcribe(
    audio_path: Path,
    onset_threshold: float = 0.5,
    frame_threshold: float = 0.3,
    min_note_length_ms: float = 60.0,
    min_frequency: float | None = None,
    max_frequency: float | None = None,
) -> list[tuple[float, float, int, float]]:
    """
    Run Basic Pitch on an audio file.
    Returns list of (start_s, end_s, midi_note, amplitude) note events.
    """
    with _silence():
        from basic_pitch.inference import predict
        _, _, note_events = predict(
            audio_path,
            onset_threshold=onset_threshold,
            frame_threshold=frame_threshold,
            minimum_note_length=min_note_length_ms,
            minimum_frequency=min_frequency,
            maximum_frequency=max_frequency,
        )

    # note_events: (start_s, end_s, midi_note, amplitude, pitch_bends_or_None)
    return [(float(s), float(e), int(n), float(a)) for s, e, n, a, _ in note_events]