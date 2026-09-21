"""AudioClip: an immutable block of decoded audio."""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

from .format import AudioFormat, SampleFormat, decode_pcm, encode_pcm
from .wavio import WavDest, WavSource, read_wav, write_wav


class AudioClip:
    """Decoded audio: ``float32`` samples shaped ``(channels, frames)`` plus a sample rate.

    Clips are treated as immutable; every operation returns a new clip and the sample array is
    marked read-only so peak caches built from it can never go stale.
    """

    __slots__ = ("_sample_rate", "_samples")

    def __init__(self, samples: np.ndarray, sample_rate: int) -> None:
        samples = np.asarray(samples, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples[np.newaxis, :]
        if samples.ndim != 2 or samples.shape[0] < 1:
            raise ValueError("samples must be 1-D (mono) or shaped (channels, frames)")
        if sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        samples = np.ascontiguousarray(samples)
        samples.setflags(write=False)
        self._samples = samples
        self._sample_rate = int(sample_rate)

    # -- constructors ---------------------------------------------------------------------------

    @classmethod
    def from_wav(cls, source: WavSource) -> AudioClip:
        samples, rate = read_wav(source)
        return cls(samples, rate)

    @classmethod
    def from_pcm(cls, data: bytes | bytearray | memoryview, fmt: AudioFormat) -> AudioClip:
        return cls(decode_pcm(data, fmt.sample_format, fmt.channels), fmt.sample_rate)

    @classmethod
    def silence(cls, seconds: float, sample_rate: int = 44100, channels: int = 1) -> AudioClip:
        return cls(np.zeros((channels, round(seconds * sample_rate)), np.float32), sample_rate)

    @classmethod
    def concatenate(cls, clips: Iterable[AudioClip]) -> AudioClip:
        clips = list(clips)
        if not clips:
            raise ValueError("nothing to concatenate")
        first = clips[0]
        if any(c.sample_rate != first.sample_rate or c.channels != first.channels for c in clips):
            raise ValueError("clips must share sample rate and channel count")
        return cls(np.concatenate([c.samples for c in clips], axis=1), first.sample_rate)

    # -- properties -----------------------------------------------------------------------------

    @property
    def samples(self) -> np.ndarray:
        return self._samples

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._samples.shape[0]

    @property
    def frames(self) -> int:
        return self._samples.shape[1]

    @property
    def duration(self) -> float:
        return self.frames / self._sample_rate

    @property
    def format(self) -> AudioFormat:
        return AudioFormat(self._sample_rate, self.channels, SampleFormat.S16)

    def __len__(self) -> int:
        return self.frames

    def __repr__(self) -> str:
        return f"AudioClip({self.channels}ch, {self._sample_rate} Hz, {self.duration:.3f}s)"

    # -- queries --------------------------------------------------------------------------------

    def channel(self, index: int) -> np.ndarray:
        return self._samples[index]

    def peak(self) -> float:
        """Largest absolute sample value across all channels (0 for an empty clip)."""
        return float(np.abs(self._samples).max()) if self.frames else 0.0

    def rms(self) -> float:
        return (
            float(np.sqrt(np.mean(np.square(self._samples, dtype=np.float64))))
            if self.frames
            else 0.0
        )

    def channel_peaks(self) -> list[float]:
        return [float(np.abs(ch).max()) if ch.size else 0.0 for ch in self._samples]

    def time_to_frame(self, seconds: float) -> int:
        return int(np.clip(round(seconds * self._sample_rate), 0, self.frames))

    # -- transforms -----------------------------------------------------------------------------

    def slice(self, start: float = 0.0, stop: float | None = None) -> AudioClip:
        a = self.time_to_frame(start)
        b = self.frames if stop is None else self.time_to_frame(stop)
        return AudioClip(self._samples[:, a : max(a, b)], self._sample_rate)

    def to_mono(self) -> AudioClip:
        if self.channels == 1:
            return self
        return AudioClip(self._samples.mean(axis=0, keepdims=True), self._sample_rate)

    def select_channels(self, indices: Iterable[int]) -> AudioClip:
        return AudioClip(self._samples[list(indices)], self._sample_rate)

    def gain(self, factor: float) -> AudioClip:
        return AudioClip(self._samples * np.float32(factor), self._sample_rate)

    # -- output ---------------------------------------------------------------------------------

    def to_pcm(self, sample_format: SampleFormat = SampleFormat.S16) -> bytes:
        return encode_pcm(self._samples, sample_format)

    def to_wav(self, dest: WavDest, sample_format: SampleFormat = SampleFormat.S16) -> None:
        write_wav(dest, self._samples, self._sample_rate, sample_format)
