"""Signal analysis used by the extra views: levels, spectrogram, stereo image, silence."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

DB_FLOOR = -96.0


def to_db(amplitude: float | np.ndarray, floor: float = DB_FLOOR) -> float | np.ndarray:
    """Linear amplitude (1.0 = full scale) to dBFS, clamped at ``floor``."""
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(np.maximum(amplitude, 1e-12))
    return np.maximum(db, floor) if isinstance(db, np.ndarray) else max(float(db), floor)


def from_db(db: float) -> float:
    return 10.0 ** (db / 20.0)


def peak_db(samples: np.ndarray) -> float:
    return to_db(float(np.abs(samples).max())) if samples.size else DB_FLOOR


def rms_db(samples: np.ndarray) -> float:
    if not samples.size:
        return DB_FLOOR
    return to_db(float(np.sqrt(np.mean(np.square(samples, dtype=np.float64)))))


# -- spectrogram ----------------------------------------------------------------------------------


@dataclass(frozen=True)
class Spectrogram:
    """Magnitude spectrogram in dBFS, shaped ``(frequency_bins, time_columns)``."""

    magnitude_db: np.ndarray
    sample_rate: int
    n_fft: int
    hop: int

    @property
    def columns(self) -> int:
        return self.magnitude_db.shape[1]

    @property
    def nyquist(self) -> float:
        return self.sample_rate / 2

    def column_time(self, column: int) -> float:
        """Centre time (seconds) of a column."""
        return (column * self.hop + self.n_fft / 2) / self.sample_rate


def spectrogram(
    samples: np.ndarray,
    sample_rate: int,
    n_fft: int = 1024,
    max_columns: int = 2400,
    floor_db: float = -100.0,
) -> Spectrogram:
    """Short-time Fourier transform of one channel.

    The hop grows for long inputs so the result never has more than ``max_columns`` columns,
    which bounds both the compute time and the size of the image later drawn from it.
    """
    x = np.asarray(samples, dtype=np.float32)
    if len(x) < n_fft:
        x = np.pad(x, (0, n_fft - len(x)))
    hop = max(n_fft // 4, int(np.ceil((len(x) - n_fft) / max(max_columns - 1, 1))))
    windows = sliding_window_view(x, n_fft)[::hop]
    window = np.hanning(n_fft).astype(np.float32)
    spectrum = np.fft.rfft(windows * window, axis=1)
    magnitude = np.abs(spectrum) * (2.0 / window.sum())
    db = np.maximum(to_db(magnitude, floor_db), floor_db).astype(np.float32)
    return Spectrogram(db.T, sample_rate, n_fft, hop)


# -- spectrum analyser ----------------------------------------------------------------------------


def band_levels(
    samples: np.ndarray,
    sample_rate: int,
    bands: int = 48,
    n_fft: int = 2048,
    f_min: float = 30.0,
    f_max: float = 16000.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Levels (dBFS) of ``bands`` log-spaced frequency bands from the last ``n_fft`` samples.

    Returns ``(centre_frequencies_hz, levels_db)``. A full-scale sine reads about 0 dB in its band.
    """
    x = np.asarray(samples, np.float32)[-n_fft:]
    if len(x) < n_fft:
        x = np.pad(x, (n_fft - len(x), 0))
    window = np.hanning(n_fft).astype(np.float32)
    magnitude = np.abs(np.fft.rfft(x * window)) * (2.0 / window.sum())
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sample_rate)

    f_max = min(f_max, sample_rate / 2 * 0.98)
    edges = np.geomspace(f_min, f_max, bands + 1)
    centres = np.sqrt(edges[:-1] * edges[1:])
    levels = np.empty(bands)
    for i in range(bands):
        in_band = (freqs >= edges[i]) & (freqs < edges[i + 1])
        if in_band.any():
            levels[i] = magnitude[in_band].max()
        else:  # a band narrower than one FFT bin: use the nearest bin instead of reading silence
            levels[i] = magnitude[int(np.argmin(np.abs(freqs - centres[i])))]
    return centres, np.asarray(to_db(levels), np.float64)


# -- stereo image ---------------------------------------------------------------------------------


def stereo_xy(left: np.ndarray, right: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Vectorscope coordinates (mid/side rotated 45 degrees): ``x = (L-R)/sqrt2``, ``y = (L+R)/sqrt2``.

    A mono signal plots as a vertical line, a hard-panned one as a diagonal.
    """
    k = np.float32(np.sqrt(0.5))
    return (left - right) * k, (left + right) * k


def correlation(left: np.ndarray, right: np.ndarray) -> float:
    """Pearson correlation of the channels: +1 mono, 0 uncorrelated, -1 out of phase."""
    if left.size < 2:
        return 0.0
    denom = float(np.std(left) * np.std(right))
    if denom < 1e-12:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


# -- silence --------------------------------------------------------------------------------------


def detect_silence(
    samples: np.ndarray,
    sample_rate: int,
    threshold_db: float = -50.0,
    min_duration: float = 0.3,
    window: float = 0.01,
) -> list[tuple[float, float]]:
    """Time ranges (seconds) whose windowed RMS stays below ``threshold_db`` for ``min_duration``."""
    hop = max(int(sample_rate * window), 1)
    usable = (len(samples) // hop) * hop
    if usable == 0:
        return []
    frames = samples[:usable].reshape(-1, hop)
    level = to_db(np.sqrt(np.mean(np.square(frames, dtype=np.float64), axis=1)))
    quiet = level < threshold_db

    ranges: list[tuple[float, float]] = []
    edges = np.flatnonzero(np.diff(np.concatenate([[0], quiet.astype(np.int8), [0]])))
    for start, end in zip(edges[::2], edges[1::2], strict=True):
        a, b = start * hop / sample_rate, end * hop / sample_rate
        if b - a >= min_duration:
            ranges.append((float(a), float(b)))
    return ranges
