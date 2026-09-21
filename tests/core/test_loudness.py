"""Loudness is checked against values that follow from BS.1770 itself, not against a reference implementation."""

import math

import numpy as np
import pytest

from audiowave import AudioClip
from audiowave.core import measure_loudness
from audiowave.core.loudness import k_weight


def sine(freq, seconds, amp, rate=48000, channels=2) -> AudioClip:
    t = np.arange(int(seconds * rate)) / rate
    return AudioClip(np.tile(amp * np.sin(2 * np.pi * freq * t), (channels, 1)), rate)


@pytest.mark.parametrize("rate", [48000, 44100, 22050, 16000])
def test_997hz_stereo_sine_reads_its_own_level(rate):
    # By design of the -0.691 offset, a stereo sine at -20 dBFS peak measures -20.0 LUFS.
    assert measure_loudness(sine(997, 6, 0.1, rate)).integrated == pytest.approx(-20.0, abs=0.15)


def test_mono_is_three_lu_below_dual_mono():
    stereo = measure_loudness(sine(997, 6, 0.1)).integrated
    mono = measure_loudness(sine(997, 6, 0.1, channels=1)).integrated
    assert stereo - mono == pytest.approx(3.01, abs=0.05)


def test_doubling_the_amplitude_adds_six_lu():
    quiet, loud = measure_loudness(sine(997, 6, 0.05)), measure_loudness(sine(997, 6, 0.1))
    assert loud.integrated - quiet.integrated == pytest.approx(6.02, abs=0.05)


def test_k_weighting_shapes_the_spectrum():
    ref = measure_loudness(sine(997, 6, 0.1)).integrated
    assert (
        2.5 < measure_loudness(sine(8000, 6, 0.1)).integrated - ref < 4.0
    )  # high shelf: about +3.5 dB
    assert measure_loudness(sine(30, 6, 0.1)).integrated - ref < -3.0  # high-pass cuts the lows


def test_k_weight_preserves_length_and_is_stable():
    x = np.random.default_rng(0).uniform(-1, 1, 200_000).astype(np.float32)
    y = k_weight(x, 48000)
    assert len(y) == len(x) and np.isfinite(y).all() and np.abs(y).max() < 10


def test_silence_and_short_clips_are_minus_infinity():
    assert measure_loudness(AudioClip.silence(3, 48000, 2)).integrated == -math.inf
    assert (
        measure_loudness(sine(997, 0.2, 0.5)).integrated == -math.inf
    )  # shorter than one 400 ms block


def test_gating_ignores_silence_but_not_quiet_music():
    loud = sine(997, 10, 0.1).samples
    gap = np.zeros((2, 48000 * 10), np.float32)
    with_gap = AudioClip(np.concatenate([loud, gap], axis=1), 48000)
    assert measure_loudness(with_gap).integrated == pytest.approx(
        -20.0, abs=0.2
    )  # silence is gated out
    # ... but a section 15 LU quieter (above the -70 absolute gate, below the -10 LU relative gate) is ignored too:
    quiet = loud * 10 ** (-15 / 20)
    mixed = AudioClip(np.concatenate([loud, quiet], axis=1), 48000)
    assert measure_loudness(mixed).integrated == pytest.approx(-20.0, abs=0.2)


def test_momentary_and_short_term_series_line_up_with_time():
    clip = AudioClip(
        np.concatenate([sine(997, 5, 0.05).samples, sine(997, 5, 0.2).samples], axis=1), 48000
    )
    m = measure_loudness(clip)
    assert len(m.momentary) == pytest.approx((10 - 0.4) / 0.1 + 1, abs=1)
    assert m.momentary_at(4.0) == pytest.approx(-26.0, abs=0.3)  # 0.05 amplitude -> -26 LUFS
    assert m.momentary_at(9.5) == pytest.approx(-14.0, abs=0.3)  # 0.2 amplitude -> -14 LUFS
    assert (
        m.momentary_at(0.1) == -math.inf and m.short_term_at(1.0) == -math.inf
    )  # before a full window
    assert m.short_term_at(10.0) > m.short_term_at(5.0)


def test_loudness_range_reflects_dynamics():
    steady = measure_loudness(sine(997, 30, 0.1)).range
    parts = []
    for i in range(6):  # alternate 10 s of loud and quiet material 12 dB apart
        parts.append(sine(997, 10, 0.2 if i % 2 == 0 else 0.05).samples)
    dynamic = measure_loudness(AudioClip(np.concatenate(parts, axis=1), 48000)).range
    assert steady < 1.0 and 8 < dynamic < 14
