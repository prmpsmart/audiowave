"""Minimal RIFF/WAVE reader and writer.

The standard-library ``wave`` module cannot read float or ``WAVE_FORMAT_EXTENSIBLE`` files, which
is what most DAWs export for 24-bit and float audio, so this reads the chunks directly.
"""

from __future__ import annotations

import io
import os
import struct
from typing import BinaryIO

import numpy as np

from .format import SampleFormat, decode_pcm, encode_pcm

WavSource = str | os.PathLike | bytes | bytearray | BinaryIO
WavDest = str | os.PathLike | BinaryIO

_TAG_PCM = 0x0001
_TAG_FLOAT = 0x0003
_TAG_EXTENSIBLE = 0xFFFE


class WavError(ValueError):
    """The data is not a WAV file this module can read."""


def _read_all(source: WavSource) -> bytes:
    if isinstance(source, bytes | bytearray):
        return bytes(source)
    if isinstance(source, str | os.PathLike):
        with open(source, "rb") as fh:
            return fh.read()
    return source.read()


def read_wav(source: WavSource) -> tuple[np.ndarray, int]:
    """Read a WAV file and return ``(samples, sample_rate)``.

    ``samples`` is ``float32`` with shape ``(channels, frames)``.
    Supports 8/16/24/32-bit PCM and 32-bit float, including the extensible header.
    """
    data = _read_all(source)
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        raise WavError("not a RIFF/WAVE file")

    fmt_info: tuple[int, int, int, int] | None = None  # tag, channels, rate, bits
    pcm: bytes | None = None
    pos = 12
    while pos + 8 <= len(data):
        chunk_id = data[pos : pos + 4]
        (size,) = struct.unpack_from("<I", data, pos + 4)
        body = pos + 8
        if chunk_id == b"fmt ":
            if size < 16:
                raise WavError("fmt chunk too small")
            tag, channels, rate, _byte_rate, _align, bits = struct.unpack_from("<HHIIHH", data, body)
            if tag == _TAG_EXTENSIBLE and size >= 26:
                (tag,) = struct.unpack_from("<H", data, body + 24)  # first 2 bytes of the sub-format GUID
            fmt_info = (tag, channels, rate, bits)
        elif chunk_id == b"data":
            # Streamed files may declare 0 or 0xFFFFFFFF; clamp to what is actually present.
            end = min(body + size, len(data)) if size not in (0, 0xFFFFFFFF) else len(data)
            pcm = data[body:end]
            if fmt_info is not None:
                break
        pos = body + size + (size & 1)

    if fmt_info is None or pcm is None:
        raise WavError("missing fmt or data chunk")
    tag, channels, rate, bits = fmt_info
    if tag not in (_TAG_PCM, _TAG_FLOAT):
        raise WavError(f"unsupported WAVE format tag: {tag:#06x}")
    if channels < 1 or rate < 1:
        raise WavError("invalid channel count or sample rate")

    sample_format = SampleFormat.from_width(bits // 8, is_float=tag == _TAG_FLOAT)
    return decode_pcm(pcm, sample_format, channels), rate


def write_wav(
    dest: WavDest,
    samples: np.ndarray,
    sample_rate: int,
    sample_format: SampleFormat = SampleFormat.S16,
) -> None:
    """Write ``(channels, frames)`` float samples as a WAV file."""
    channels = samples.shape[0]
    pcm = encode_pcm(samples, sample_format)
    width = sample_format.width
    tag = _TAG_FLOAT if sample_format is SampleFormat.F32 else _TAG_PCM
    header = b"".join(
        [
            b"RIFF",
            struct.pack("<I", 36 + len(pcm) + (len(pcm) & 1)),
            b"WAVEfmt ",
            struct.pack("<IHHIIHH", 16, tag, channels, sample_rate, sample_rate * channels * width, channels * width, width * 8),
            b"data",
            struct.pack("<I", len(pcm)),
        ]
    )
    payload = header + pcm + (b"\x00" if len(pcm) & 1 else b"")

    if isinstance(dest, str | os.PathLike):
        with open(dest, "wb") as fh:
            fh.write(payload)
    else:
        dest.write(payload)


def wav_bytes(samples: np.ndarray, sample_rate: int, sample_format: SampleFormat = SampleFormat.S16) -> bytes:
    """Convenience: encode to an in-memory WAV file."""
    buffer = io.BytesIO()
    write_wav(buffer, samples, sample_rate, sample_format)
    return buffer.getvalue()
