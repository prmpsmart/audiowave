"""Waveform envelopes.

A waveform widget needs, for each horizontal bucket, the minimum, maximum and RMS of the samples
that fall into it. Recomputing that from millions of samples on every zoom or resize is too slow,
so ``PeakPyramid`` precomputes progressively coarser levels (like mip-maps) and answers any
``query(start, stop, buckets)`` from the nearest level.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .clip import AudioClip


@dataclass(frozen=True)
class Peaks:
    """Per-bucket envelope of one channel. All arrays have the same length."""

    minimum: np.ndarray
    maximum: np.ndarray
    rms: np.ndarray

    def __len__(self) -> int:
        return len(self.maximum)

    @property
    def amplitude(self) -> np.ndarray:
        """Half the peak-to-peak span, i.e. a symmetric ("average") amplitude per bucket."""
        return (self.maximum - self.minimum) * 0.5

    @classmethod
    def zeros(cls, buckets: int) -> Peaks:
        z = np.zeros(max(buckets, 0), np.float32)
        return cls(z, z.copy(), z.copy())

    @classmethod
    def concatenate(cls, parts: list[Peaks]) -> Peaks:
        if not parts:
            return cls.zeros(0)
        return cls(
            np.concatenate([p.minimum for p in parts]),
            np.concatenate([p.maximum for p in parts]),
            np.concatenate([p.rms for p in parts]),
        )


def _reduce_segments(
    mn: np.ndarray, mx: np.ndarray, sq: np.ndarray, cnt: np.ndarray, edges: np.ndarray
) -> Peaks:
    """Reduce ``[edges[i], edges[i+1])`` for every ``i``; a segment is never empty (min 1 element).

    ``ufunc.reduceat`` returns the single element at ``edges[i]`` when ``edges[i] >= edges[i+1]``,
    which is exactly the behaviour wanted when there are more buckets than source values.
    """
    n = len(mn)
    if n == 0:
        return Peaks.zeros(len(edges) - 1)
    end = min(max(int(edges[-1]), 1), n)
    starts = np.minimum(edges[:-1], end - 1)
    mn_r = np.minimum.reduceat(mn[:end], starts)
    mx_r = np.maximum.reduceat(mx[:end], starts)
    sq_r = np.add.reduceat(sq[:end], starts)
    cnt_r = np.add.reduceat(cnt[:end], starts)
    rms = np.sqrt(sq_r / np.maximum(cnt_r, 1.0))
    return Peaks(mn_r.astype(np.float32), mx_r.astype(np.float32), rms.astype(np.float32))


@dataclass(frozen=True)
class _Level:
    block: int  # source samples per entry
    mn: np.ndarray
    mx: np.ndarray
    sq: np.ndarray  # sum of squares (float64)
    cnt: np.ndarray  # samples represented (float64)


class PeakPyramid:
    """Multi-resolution min/max/RMS index over one channel."""

    def __init__(self, samples: np.ndarray, base_block: int = 64) -> None:
        x = np.ascontiguousarray(samples, dtype=np.float32)
        self._samples = x
        self._base = base_block
        self._levels: list[_Level] = []
        n = len(x)
        if n == 0:
            return
        starts = np.arange(0, n, base_block)
        level = _Level(
            block=base_block,
            mn=np.minimum.reduceat(x, starts),
            mx=np.maximum.reduceat(x, starts),
            sq=np.add.reduceat(x * x, starts, dtype=np.float64),
            cnt=np.diff(np.append(starts, n)).astype(np.float64),
        )
        self._levels.append(level)
        while len(level.mn) > 2:
            pair = np.arange(0, len(level.mn), 2)
            level = _Level(
                block=level.block * 2,
                mn=np.minimum.reduceat(level.mn, pair),
                mx=np.maximum.reduceat(level.mx, pair),
                sq=np.add.reduceat(level.sq, pair),
                cnt=np.add.reduceat(level.cnt, pair),
            )
            self._levels.append(level)

    @property
    def frames(self) -> int:
        return len(self._samples)

    def query(self, start: int, stop: int, buckets: int) -> Peaks:
        """Envelope of frames ``[start, stop)`` split into ``buckets`` equal buckets."""
        if buckets <= 0:
            return Peaks.zeros(0)
        n = self.frames
        start = int(np.clip(start, 0, n))
        stop = int(np.clip(stop, 0, n))
        if stop <= start:
            return Peaks.zeros(buckets)

        per_bucket = (stop - start) / buckets
        level = self._pick_level(per_bucket)
        if level is None:
            return self._direct(start, stop, buckets)

        edges = np.linspace(start / level.block, stop / level.block, buckets + 1)
        edges = np.rint(edges).astype(np.int64)
        edges[-1] = max(edges[-1], int(np.ceil(stop / level.block)))
        return _reduce_segments(level.mn, level.mx, level.sq, level.cnt, edges)

    def _pick_level(self, per_bucket: float) -> _Level | None:
        chosen = None
        for level in self._levels:
            if level.block <= per_bucket / 2:  # keep >= 2 source entries per bucket for accuracy
                chosen = level
            else:
                break
        return chosen

    def _direct(self, start: int, stop: int, buckets: int) -> Peaks:
        x = self._samples[start:stop]
        edges = np.linspace(0, len(x), buckets + 1).astype(np.int64)
        return _reduce_segments(x, x, x * x, np.ones(len(x), np.float64), edges)


class ClipPeaks:
    """Peak pyramids for every channel of a clip."""

    def __init__(self, clip: AudioClip, base_block: int = 64) -> None:
        self.sample_rate = clip.sample_rate
        self.frames = clip.frames
        self.pyramids = [PeakPyramid(clip.channel(i), base_block) for i in range(clip.channels)]

    @property
    def channels(self) -> int:
        return len(self.pyramids)

    @property
    def duration(self) -> float:
        return self.frames / self.sample_rate

    def query(self, start: float, stop: float, buckets: int) -> list[Peaks]:
        """Per-channel envelopes for the time range ``[start, stop)`` in seconds."""
        a = int(round(start * self.sample_rate))
        b = int(round(stop * self.sample_rate))
        return [p.query(a, b, buckets) for p in self.pyramids]
