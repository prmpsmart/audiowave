"""Programme loudness per ITU-R BS.1770-4 / EBU R128: momentary, short-term, integrated and range.

K-weighting (a high shelf plus a high-pass) is an IIR filter. Running a biquad sample by sample in
Python is far too slow, so its impulse response, which dies away within a few milliseconds, is
truncated and applied by block FFT convolution instead. The truncation error is around 1e-6.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .clip import AudioClip

BLOCK_SECONDS = 0.4  # momentary window
SHORT_TERM_SECONDS = 3.0
HOP_SECONDS = 0.1  # 75 % overlap of the momentary window
ABSOLUTE_GATE = -70.0  # LUFS
RELATIVE_GATE = -10.0  # LU below the ungated mean (integrated loudness)
RANGE_GATE = -20.0  # LU below the ungated mean (loudness range)
_OFFSET = -0.691
_IR_SECONDS = 0.25


@dataclass(frozen=True)
class Loudness:
    """Loudness of a clip. Arrays hold one value per ``hop`` seconds; values are in LUFS."""

    momentary: np.ndarray
    short_term: np.ndarray
    integrated: float  # gated; -inf when the clip is too short or too quiet to measure
    range: float  # LRA in LU; 0 when there is not enough material
    hop: float = HOP_SECONDS

    def momentary_at(self, seconds: float) -> float:
        """Momentary loudness of the 400 ms window ending at ``seconds`` (-inf before the first full window)."""
        return _sample(self.momentary, seconds - BLOCK_SECONDS, self.hop)

    def short_term_at(self, seconds: float) -> float:
        return _sample(self.short_term, seconds - SHORT_TERM_SECONDS, self.hop)


def _sample(values: np.ndarray, start: float, hop: float) -> float:
    i = round(start / hop)
    return float(values[i]) if 0 <= i < len(values) else -math.inf


def _biquads(fs: float) -> list[tuple[np.ndarray, np.ndarray]]:
    """K-weighting stages as ``(b, a)`` with ``a[0] == 1``, for any sample rate (BS.1770 gives 48 kHz only)."""
    # Stage 1: high shelf, +4 dB above ~1.7 kHz (models the head).
    f0, gain_db, q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    k = math.tan(math.pi * f0 / fs)
    vh = 10 ** (gain_db / 20)
    vb = vh**0.4996667741545416
    a0 = 1 + k / q + k * k
    shelf_b = np.array([vh + vb * k / q + k * k, 2 * (k * k - vh), vh - vb * k / q + k * k]) / a0
    shelf_a = np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    # Stage 2: high-pass at ~38 Hz (revised low-frequency B-weighting).
    f0, q = 38.13547087602444, 0.5003270373238773
    k = math.tan(math.pi * f0 / fs)
    a0 = 1 + k / q + k * k
    hp_b = np.array([1.0, -2.0, 1.0])
    hp_a = np.array([1.0, 2 * (k * k - 1) / a0, (1 - k / q + k * k) / a0])
    return [(shelf_b, shelf_a), (hp_b, hp_a)]


def _impulse_response(fs: float) -> np.ndarray:
    n = int(fs * _IR_SECONDS)
    signal = np.zeros(n)
    signal[0] = 1.0
    for b, a in _biquads(fs):  # direct form I, once, on an impulse: cheap
        out = np.zeros(n)
        x1 = x2 = y1 = y2 = 0.0
        for i in range(n):
            x0 = signal[i]
            y0 = b[0] * x0 + b[1] * x1 + b[2] * x2 - a[1] * y1 - a[2] * y2
            out[i] = y0
            x2, x1, y2, y1 = x1, x0, y1, y0
        signal = out
    return signal


def k_weight(samples: np.ndarray, fs: float) -> np.ndarray:
    """Apply BS.1770 K-weighting to one channel (returns float64, same length)."""
    h = _impulse_response(fs)
    n, taps = len(samples), len(h)
    block = 1 << 16
    size = 1 << (block + taps - 1).bit_length()
    h_fft = np.fft.rfft(h, size)
    out = np.zeros(n + taps - 1)
    for start in range(0, n, block):
        chunk = samples[start : start + block].astype(np.float64)
        spectrum = np.fft.rfft(chunk, size) * h_fft
        out[start : start + len(chunk) + taps - 1] += np.fft.irfft(spectrum, size)[
            : len(chunk) + taps - 1
        ]
    return out[:n]


def _lufs(power: np.ndarray | float) -> np.ndarray | float:
    with np.errstate(divide="ignore"):
        return _OFFSET + 10 * np.log10(power)


def _gated_mean_power(power: np.ndarray, relative: float) -> float:
    """Mean power of blocks above the absolute gate and ``relative`` LU below their ungated mean; NaN if none."""
    loud = power[_lufs(power) > ABSOLUTE_GATE]
    if not len(loud):
        return math.nan
    threshold = _lufs(loud.mean()) + relative
    kept = loud[_lufs(loud) > threshold]
    return float(kept.mean()) if len(kept) else math.nan


def measure_loudness(clip: AudioClip) -> Loudness:
    """Momentary, short-term, integrated loudness and range of ``clip``."""
    fs = clip.sample_rate
    hop = max(round(HOP_SECONDS * fs), 1)
    hops = clip.frames // hop
    per_hop = np.zeros(hops)
    for c in range(clip.channels):  # all channels weighted 1.0; surround weights are not modelled
        weighted = k_weight(clip.channel(c), fs)[: hops * hop]
        per_hop += np.square(weighted).reshape(hops, hop).sum(axis=1)
    per_hop /= hop  # mean square of each 100 ms hop, summed over channels

    def window_power(seconds: float) -> np.ndarray:
        n = round(seconds / HOP_SECONDS)
        if hops < n:
            return np.zeros(0)
        return np.convolve(per_hop, np.ones(n) / n, mode="valid")

    momentary_power = window_power(BLOCK_SECONDS)
    short_power = window_power(SHORT_TERM_SECONDS)

    integrated_power = _gated_mean_power(momentary_power, RELATIVE_GATE)
    integrated = -math.inf if math.isnan(integrated_power) else float(_lufs(integrated_power))
    return Loudness(
        momentary=np.asarray(_lufs(momentary_power), np.float64),
        short_term=np.asarray(_lufs(short_power), np.float64),
        integrated=integrated,
        range=_loudness_range(short_power),
    )


def _loudness_range(short_power: np.ndarray) -> float:
    kept_power = short_power[_lufs(short_power) > ABSOLUTE_GATE]
    if not len(kept_power):
        return 0.0
    threshold = _lufs(kept_power.mean()) + RANGE_GATE
    levels = _lufs(kept_power)[_lufs(kept_power) > threshold]
    if len(levels) < 2:
        return 0.0
    return float(np.percentile(levels, 95) - np.percentile(levels, 10))
