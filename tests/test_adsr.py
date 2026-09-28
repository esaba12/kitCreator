import numpy as np

from kitforge.extract.adsr import estimate_adsr

SR = 44100


def test_silence_returns_default():
    audio = np.zeros(SR, dtype=np.float32)
    adsr = estimate_adsr(audio, SR)
    assert adsr.attack == 0.01
    assert adsr.sustain == 100.0


def test_percussive_one_shot_has_short_attack_and_no_sustain_plateau():
    t = np.linspace(0, 0.5, int(0.5 * SR), endpoint=False)
    audio = np.exp(-t * 15.0).astype(np.float32)  # fast attack, free decay to ~0
    adsr = estimate_adsr(audio, SR)
    assert adsr.attack < 0.02
    assert adsr.sustain < 50.0


def test_sustained_tone_has_high_sustain_level():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    envelope = np.ones_like(t)
    envelope[: int(0.01 * SR)] = np.linspace(0, 1, int(0.01 * SR))  # 10ms attack ramp
    audio = (envelope * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    adsr = estimate_adsr(audio, SR)
    assert adsr.sustain > 80.0


def test_slow_attack_is_measured_after_peak_delay():
    t = np.linspace(0, 1.0, SR, endpoint=False)
    ramp = np.clip(t / 0.3, 0, 1)  # 300ms linear ramp to full level
    audio = (ramp * np.sin(2 * np.pi * 220.0 * t)).astype(np.float32)
    adsr = estimate_adsr(audio, SR)
    assert adsr.attack > 0.2
