"""Wire format for streaming audio between two studio instances.

Every message is ``[type: u8][length: u32 LE][payload]``. Length-prefixing replaces the old
``<<>>`` delimiter, which broke whenever audio bytes happened to contain that sequence, and lets
the receiver tell where a frame ends however the TCP stream is chopped up.
"""

from __future__ import annotations

import json
import struct
from dataclasses import dataclass
from enum import IntEnum

from audiowave import AudioFormat, SampleFormat

PORT_RANGE = (6000, 9000)
FRAME_MS = 20
MAX_PAYLOAD = 1 << 20  # refuse absurd lengths from a misbehaving peer

_HEADER = struct.Struct("<BI")


class ProtocolError(ValueError):
    """The peer sent something that is not valid protocol data."""


class MessageType(IntEnum):
    HELLO = 1  # JSON: the audio format that follows
    FRAME = 2  # raw interleaved signed 16-bit PCM
    END = 3  # the sender has no more audio


@dataclass(frozen=True)
class Message:
    type: MessageType
    payload: bytes = b""


def valid_port(port: int) -> bool:
    return PORT_RANGE[0] <= port <= PORT_RANGE[1]


def _pack(kind: MessageType, payload: bytes = b"") -> bytes:
    return _HEADER.pack(kind, len(payload)) + payload


def encode_hello(sample_rate: int, channels: int) -> bytes:
    return _pack(
        MessageType.HELLO,
        json.dumps({"rate": sample_rate, "channels": channels, "format": "s16"}).encode(),
    )


def encode_frame(pcm: bytes) -> bytes:
    return _pack(MessageType.FRAME, pcm)


def encode_end() -> bytes:
    return _pack(MessageType.END)


def parse_hello(payload: bytes) -> AudioFormat:
    try:
        data = json.loads(payload)
        if data.get("format") != "s16":
            raise ProtocolError(f"unsupported sample format: {data.get('format')!r}")
        return AudioFormat(int(data["rate"]), int(data["channels"]), SampleFormat.S16)
    except (ValueError, KeyError, TypeError) as error:
        if isinstance(error, ProtocolError):
            raise
        raise ProtocolError(f"bad HELLO: {error}") from error


def split_pcm(pcm: bytes, fmt: AudioFormat, frame_ms: int = FRAME_MS) -> list[bytes]:
    """Cut PCM into whole-sample-frame chunks of roughly ``frame_ms`` each."""
    step = max(int(fmt.sample_rate * frame_ms / 1000), 1) * fmt.bytes_per_frame
    usable = len(pcm) - len(pcm) % fmt.bytes_per_frame
    return [pcm[i : min(i + step, usable)] for i in range(0, usable, step)]


class FrameDecoder:
    """Reassembles messages from arbitrary byte chunks (TCP gives no message boundaries)."""

    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Message]:
        self._buffer += data
        messages: list[Message] = []
        while len(self._buffer) >= _HEADER.size:
            kind, length = _HEADER.unpack_from(self._buffer)
            if length > MAX_PAYLOAD:
                raise ProtocolError(f"payload too large: {length}")
            try:
                message_type = MessageType(kind)
            except ValueError:
                raise ProtocolError(f"unknown message type: {kind}") from None
            end = _HEADER.size + length
            if len(self._buffer) < end:
                break
            messages.append(Message(message_type, bytes(self._buffer[_HEADER.size : end])))
            del self._buffer[:end]
        return messages

    def reset(self) -> None:
        self._buffer.clear()
