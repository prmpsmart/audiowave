"""Synthetic audio so the app has something to show before a file is opened."""

from __future__ import annotations

import numpy as np

from audiowave import AudioClip, ClipPeaks, Peaks


def demo_clip(seconds: float = 8.0, sample_rate: int = 22050) -> AudioClip:
    """A stereo, speech-like signal: a gliding harmonic tone gated into phrases."""
    n = int(seconds * sample_rate)
    t = np.arange(n) / sample_rate
    rng = np.random.default_rng(7)

    phrases = (
        np.clip(
            0.55 + 0.6 * np.sin(t * 2.3 + 0.4) * np.sin(t * 0.9 + 1.1) + 0.15 * np.sin(t * 9.7),
            0,
            1,
        )
        ** 1.5
    )
    pitch = 150 + 55 * np.sin(t * 1.7) + 25 * np.sin(t * 5.3)
    phase = 2 * np.pi * np.cumsum(pitch) / sample_rate
    voiced = sum(np.sin(k * phase) * 0.7**k for k in range(1, 9))
    breath = rng.normal(0, 0.012, n)
    mono = (voiced * 0.45 + breath) * phrases

    left = mono + 0.10 * np.sin(2 * np.pi * 3.0 * t) * mono
    right = np.roll(mono, 90) * 0.92 + 0.05 * rng.normal(
        0, 0.05, n
    )  # slight delay: a believable stereo image
    stereo = np.stack([left, right]).astype(np.float32)
    return AudioClip(stereo / max(np.abs(stereo).max(), 1e-6) * 0.85, sample_rate)


def demo_peaks(
    buckets: int,
    clip: AudioClip | None = None,
    start: float = 0.0,
    stop: float | None = None,
) -> Peaks:
    """Envelope of the demo (or given) clip's first channel, for thumbnails and previews."""
    clip = clip or demo_clip()
    return ClipPeaks(clip).query(start, clip.duration if stop is None else stop, buckets)[0]
