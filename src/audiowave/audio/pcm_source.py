"""PcmSource: the byte stream a QAudioSink pulls from, with a gapless loop region."""

from __future__ import annotations

from PySide6.QtCore import QIODevice

_UNBOUNDED = 1 << 30


class PcmSource(QIODevice):
    """Serves interleaved PCM bytes from memory.

    All positions are in *frames*. When a loop is set and playback reaches its end, the read
    continues from the loop start inside the same ``readData`` call, so there is no audible gap.
    A loop is only entered if playback starts at or before its end.
    """

    def __init__(self, pcm: bytes, bytes_per_frame: int) -> None:
        super().__init__()
        self._pcm = pcm
        self._bpf = bytes_per_frame
        self._total = len(pcm) // bytes_per_frame
        self._pos = 0
        self._loop: tuple[int, int] | None = None

    # -- state ----------------------------------------------------------------------------------

    @property
    def total_frames(self) -> int:
        return self._total

    @property
    def frame(self) -> int:
        """Next frame that will be handed to the sink."""
        return self._pos

    @property
    def exhausted(self) -> bool:
        return self._loop is None and self._pos >= self._total

    def seek_frame(self, frame: int) -> None:
        self._pos = min(max(frame, 0), self._total)

    def set_loop(self, start: int | None, end: int | None = None) -> None:
        """Loop ``[start, end)`` frames, or clear the loop with ``None``."""
        if start is None or end is None or end - start < 1:
            self._loop = None
        else:
            self._loop = (max(start, 0), min(end, self._total))

    def open_for_playback(self) -> bool:
        """Open read-only and *unbuffered*.

        Buffered QIODevices read ahead in large chunks, which would advance ``frame`` far beyond
        what the sink has consumed and break seek and position accounting.
        """
        return self.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Unbuffered)

    # -- QIODevice ------------------------------------------------------------------------------

    def isSequential(self) -> bool:
        return True

    def bytesAvailable(self) -> int:
        remaining = _UNBOUNDED if self._loop else (self._total - self._pos) * self._bpf
        return remaining + super().bytesAvailable()

    def readData(self, maxlen: int) -> bytes:
        want = maxlen - maxlen % self._bpf
        out = bytearray()
        while want > 0:
            if self._loop and self._pos == self._loop[1]:
                self._pos = self._loop[0]
            limit = self._loop[1] if self._loop and self._pos < self._loop[1] else self._total
            frames = min(limit - self._pos, want // self._bpf)
            if frames <= 0:
                break
            start = self._pos * self._bpf
            out += self._pcm[start : start + frames * self._bpf]
            self._pos += frames
            want -= frames * self._bpf
        return bytes(out)

    def writeData(self, data, len) -> int:  # noqa: A002 - Qt's signature
        return -1
