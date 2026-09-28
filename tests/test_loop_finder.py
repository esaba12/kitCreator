import numpy as np

from kitforge.extract.loop_finder import find_loop

SR = 44100


def test_too_short_returns_none():
    audio = np.zeros(int(0.1 * SR), dtype=np.float32)
    assert find_loop(audio, SR) is None


def test_silence_returns_none():
    audio = np.zeros(SR, dtype=np.float32)
    assert find_loop(audio, SR) is None


def test_decaying_signal_returns_none():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    audio = (np.exp(-t * 8.0) * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    assert find_loop(audio, SR) is None


def test_sustained_periodic_tone_finds_loop_near_expected_period():
    freq = 220.0
    t = np.linspace(0, 1.0, SR, endpoint=False)
    audio = np.sin(2 * np.pi * freq * t).astype(np.float32)
    result = find_loop(audio, SR)
    assert result is not None
    loop_start, loop_end = result
    assert 0 <= loop_start < loop_end < len(audio)

    expected_period = SR / freq
    loop_len = loop_end - loop_start
    n_periods_est = round(loop_len / expected_period)
    assert n_periods_est >= 1
    assert abs(loop_len - n_periods_est * expected_period) < expected_period * 0.5


def test_white_noise_has_no_clean_period():
    rng = np.random.default_rng(0)
    audio = rng.uniform(-1.0, 1.0, SR).astype(np.float32)
    assert find_loop(audio, SR) is None
