"""PCM sample formats and the (de)interleaving between raw bytes and float arrays.

Everything above this module works on ``float32`` arrays shaped ``(channels, frames)`` in the
range ``[-1, 1]``. This is the only place that knows about integer sample widths.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


class SampleFormat(Enum):
    """Sample encodings that can be decoded from / encoded to raw PCM bytes."""

    U8 = "u8"
    S16 = "s16"
    S24 = "s24"
    S32 = "s32"
    F32 = "f32"

    @property
    def width(self) -> int:
        """Bytes per sample."""
        return _WIDTHS[self]

    @classmethod
    def from_width(cls, width: int, *, is_float: bool = False) -> SampleFormat:
        if is_float:
            if width == 4:
                return cls.F32
            raise ValueError(f"unsupported float sample width: {width}")
        try:
            return _BY_WIDTH[width]
        except KeyError:
            raise ValueError(f"unsupported PCM sample width: {width}") from None


_WIDTHS = {
    SampleFormat.U8: 1,
    SampleFormat.S16: 2,
    SampleFormat.S24: 3,
    SampleFormat.S32: 4,
    SampleFormat.F32: 4,
}
_BY_WIDTH = {
    1: SampleFormat.U8,
    2: SampleFormat.S16,
    3: SampleFormat.S24,
    4: SampleFormat.S32,
}


@dataclass(frozen=True)
class AudioFormat:
    """Describes a stream of interleaved PCM frames."""

    sample_rate: int
    channels: int
    sample_format: SampleFormat = SampleFormat.S16

    def __post_init__(self) -> None:
        if self.sample_rate <= 0:
            raise ValueError("sample_rate must be positive")
        if self.channels <= 0:
            raise ValueError("channels must be positive")

    @property
    def bytes_per_frame(self) -> int:
        return self.channels * self.sample_format.width

    @property
    def bytes_per_second(self) -> int:
        return self.bytes_per_frame * self.sample_rate


def decode_pcm(
    data: bytes | bytearray | memoryview, fmt: SampleFormat, channels: int
) -> np.ndarray:
    """Decode interleaved PCM bytes into a ``float32`` array of shape ``(channels, frames)``.

    A trailing partial frame is dropped rather than raising, so a stream cut mid-frame is still usable.
    """
    if channels <= 0:
        raise ValueError("channels must be positive")
    frame_bytes = fmt.width * channels
    usable = len(data) - (len(data) % frame_bytes)
    raw = np.frombuffer(data, dtype=np.uint8, count=usable)

    if fmt is SampleFormat.U8:
        values = (raw.astype(np.float32) - 128.0) / 128.0
    elif fmt is SampleFormat.S16:
        values = raw.view("<i2").astype(np.float32) / 32768.0
    elif fmt is SampleFormat.S24:
        b = raw.reshape(-1, 3).astype(np.int32)
        packed = b[:, 0] | (b[:, 1] << 8) | (b[:, 2] << 16)
        values = ((packed ^ 0x800000) - 0x800000).astype(np.float32) / 8388608.0
    elif fmt is SampleFormat.S32:
        values = (raw.view("<i4").astype(np.float64) / 2147483648.0).astype(np.float32)
    elif fmt is SampleFormat.F32:
        values = raw.view("<f4").astype(np.float32, copy=True)
    else:  # pragma: no cover - exhaustive enum
        raise ValueError(f"unsupported format: {fmt}")

    return np.ascontiguousarray(values.reshape(-1, channels).T)


def encode_pcm(samples: np.ndarray, fmt: SampleFormat) -> bytes:
    """Encode a ``(channels, frames)`` float array into interleaved PCM bytes, clipping to range."""
    if samples.ndim != 2:
        raise ValueError("samples must have shape (channels, frames)")
    interleaved = np.clip(samples.T, -1.0, 1.0).reshape(-1)

    if fmt is SampleFormat.U8:
        # Same 128 scale as decode_pcm so the round trip is exact to one quantisation step.
        return np.clip(np.round(interleaved * 128.0 + 128.0), 0, 255).astype(np.uint8).tobytes()
    if fmt is SampleFormat.S16:
        return np.round(interleaved * 32767.0).astype("<i2").tobytes()
    if fmt is SampleFormat.S24:
        ints = np.round(interleaved.astype(np.float64) * 8388607.0).astype("<i4")
        return ints.view(np.uint8).reshape(-1, 4)[:, :3].tobytes()
    if fmt is SampleFormat.S32:
        return np.round(interleaved.astype(np.float64) * 2147483647.0).astype("<i4").tobytes()
    if fmt is SampleFormat.F32:
        return interleaved.astype("<f4").tobytes()
    raise ValueError(f"unsupported format: {fmt}")  # pragma: no cover
