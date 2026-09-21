"""Incremental envelope for audio that is still arriving (recording, network stream)."""

from __future__ import annotations

import numpy as np

from .peaks import Peaks


class LivePeaks:
    """Accumulates min/max/RMS buckets of a fixed size as sample chunks are appended.

    Unlike ``PeakPyramid`` the bucket size is fixed at ``samples_per_bucket`` frames, so a bucket's
    value never changes once it has been completed and appending is O(chunk size).
    """

    def __init__(self, channels: int, samples_per_bucket: int = 512) -> None:
        if channels < 1 or samples_per_bucket < 1:
            raise ValueError("channels and samples_per_bucket must be positive")
        self.channels = channels
        self.samples_per_bucket = samples_per_bucket
        self.clear()

    def clear(self) -> None:
        self.frames = 0
        self._carry = np.zeros((self.channels, 0), np.float32)
        self._mn: list[list[np.ndarray]] = [[] for _ in range(self.channels)]
        self._mx: list[list[np.ndarray]] = [[] for _ in range(self.channels)]
        self._sq: list[list[np.ndarray]] = [[] for _ in range(self.channels)]
        self._cache: list[Peaks] | None = None

    def append(self, samples: np.ndarray) -> None:
        """Append a ``(channels, frames)`` chunk."""
        if samples.ndim != 2 or samples.shape[0] != self.channels:
            raise ValueError(f"expected shape ({self.channels}, n), got {samples.shape}")
        if samples.shape[1] == 0:
            return
        self.frames += samples.shape[1]
        data = np.concatenate([self._carry, samples.astype(np.float32, copy=False)], axis=1)
        spb = self.samples_per_bucket
        whole = (data.shape[1] // spb) * spb
        if whole:
            blocks = data[:, :whole].reshape(self.channels, -1, spb)
            for c in range(self.channels):
                self._mn[c].append(blocks[c].min(axis=1))
                self._mx[c].append(blocks[c].max(axis=1))
                self._sq[c].append(np.square(blocks[c], dtype=np.float64).sum(axis=1))
        self._carry = data[:, whole:]
        self._cache = None

    @property
    def duration_frames(self) -> int:
        return self.frames

    def peaks(self) -> list[Peaks]:
        """Per-channel envelope including the partially filled last bucket."""
        if self._cache is None:
            self._cache = [self._channel_peaks(c) for c in range(self.channels)]
        return self._cache

    def tail(self, buckets: int) -> list[Peaks]:
        """The most recent ``buckets`` buckets of each channel (fewer if not yet available)."""
        return [
            Peaks(p.minimum[-buckets:], p.maximum[-buckets:], p.rms[-buckets:])
            for p in self.peaks()
        ]

    def _channel_peaks(self, c: int) -> Peaks:
        spb = self.samples_per_bucket
        if self._mn[c]:
            mn = np.concatenate(self._mn[c])
            mx = np.concatenate(self._mx[c])
            rms = np.sqrt(np.concatenate(self._sq[c]) / spb)
        else:
            mn = mx = rms = np.zeros(0)
        rest = self._carry[c]
        if rest.size:
            mn = np.append(mn, rest.min())
            mx = np.append(mx, rest.max())
            rms = np.append(rms, np.sqrt(np.mean(np.square(rest, dtype=np.float64))))
        return Peaks(mn.astype(np.float32), mx.astype(np.float32), rms.astype(np.float32))
