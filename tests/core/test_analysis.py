import numpy as np
import pytest

from audiowave.core import (
    correlation, detect_silence, from_db, peak_db, rms_db, spectrogram, stereo_xy, to_db,
)


def test_db_conversions():
    assert to_db(1.0) == pytest.approx(0.0) and to_db(0.5) == pytest.approx(-6.02, abs=0.01)
    assert to_db(0.0) == -96.0 and from_db(-20) == pytest.approx(0.1)
    assert peak_db(np.array([0.1, -0.5], np.float32)) == pytest.approx(to_db(0.5))
    assert rms_db(np.zeros(0, np.float32)) == -96.0


def test_spectrogram_finds_the_tone(sine):
    spec = spectrogram(sine.channel(0), sine.sample_rate, n_fft=1024)
    bin_hz = sine.sample_rate / 1024
    loudest = spec.magnitude_db.mean(axis=1).argmax()
    assert abs(loudest * bin_hz - 440) <= bin_hz
    assert spec.magnitude_db.shape[0] == 513 and spec.nyquist == 4000


def test_spectrogram_column_cap_and_short_input():
    x = np.random.default_rng(3).uniform(-1, 1, 400_000).astype(np.float32)
    assert spectrogram(x, 44100, max_columns=500).columns <= 500
    assert spectrogram(np.zeros(10, np.float32), 8000).columns >= 1


def test_stereo_xy_and_correlation():
    m = np.sin(np.linspace(0, 20, 500)).astype(np.float32)
    x, y = stereo_xy(m, m)  # identical channels: pure mid
    assert np.abs(x).max() < 1e-6 and np.abs(y).max() > 1.0
    assert correlation(m, m) == pytest.approx(1.0) and correlation(m, -m) == pytest.approx(-1.0)
    assert correlation(m, np.zeros_like(m)) == 0.0


def test_detect_silence_finds_the_gap():
    sr = 1000
    x = np.concatenate([np.full(1000, 0.5), np.zeros(800), np.full(1000, 0.5)]).astype(np.float32)
    ranges = detect_silence(x, sr, min_duration=0.3)
    assert len(ranges) == 1
    assert ranges[0][0] == pytest.approx(1.0, abs=0.02) and ranges[0][1] == pytest.approx(1.8, abs=0.02)
    assert detect_silence(x, sr, min_duration=2.0) == []
    assert detect_silence(np.zeros(0, np.float32), sr) == []
