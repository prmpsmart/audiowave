"""Decode compressed audio (mp3, flac, ogg, m4a, ...) into an AudioClip using Qt's FFmpeg-backed decoder.

WAV is read by the Qt-free core; everything else goes through ``QAudioDecoder``, so there is no extra
dependency and any format the platform's FFmpeg build supports works.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudioDecoder, QAudioFormat

from audiowave.core.clip import AudioClip

#: Extensions offered in file dialogs. Decoding itself probes the content, so others may work too.
SUPPORTED_EXTENSIONS = (".wav", ".mp3", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".wma")
FILE_DIALOG_FILTER = (
    "Audio (" + " ".join(f"*{e}" for e in SUPPORTED_EXTENSIONS) + ");;All files (*)"
)


class DecodeError(RuntimeError):
    """The file could not be decoded."""


def is_supported(path: str | Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


class AudioDecoder(QObject):
    """Decodes one file at a time in the background of the event loop.

    Emits ``progress`` (0..1, when the duration is known) and then either ``decoded(clip)`` or
    ``failed(message)``. Starting a new decode cancels the previous one.
    """

    decoded = Signal(object)  # AudioClip
    failed = Signal(str)
    progress = Signal(float)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._decoder: QAudioDecoder | None = None
        self._chunks: list[np.ndarray] = []
        self._rate = 0
        self._channels = 0

    @property
    def is_running(self) -> bool:
        return self._decoder is not None

    def decode(self, path: str | Path) -> None:
        self.cancel()
        path = Path(path)
        if not path.is_file():
            self.failed.emit(f"File not found: {path}")
            return
        self._chunks, self._rate, self._channels = [], 0, 0

        decoder = QAudioDecoder(self)
        fmt = QAudioFormat()
        fmt.setSampleFormat(
            QAudioFormat.SampleFormat.Float
        )  # sample rate and channels stay as in the file
        decoder.setAudioFormat(fmt)
        decoder.setSource(QUrl.fromLocalFile(str(path)))
        decoder.bufferReady.connect(self._on_buffer)
        decoder.finished.connect(self._on_finished)
        decoder.error.connect(self._on_error)
        self._decoder = decoder
        decoder.start()

    def cancel(self) -> None:
        if self._decoder is not None:
            self._release()

    # -- internals ------------------------------------------------------------------------------

    def _on_buffer(self) -> None:
        decoder = self._decoder
        if decoder is None:
            return
        buffer = decoder.read()
        fmt = buffer.format()
        if not buffer.isValid() or fmt.sampleFormat() != QAudioFormat.SampleFormat.Float:
            return
        self._rate, self._channels = fmt.sampleRate(), fmt.channelCount()
        interleaved = np.frombuffer(bytes(buffer.constData()), np.float32)
        usable = len(interleaved) - len(interleaved) % self._channels
        self._chunks.append(interleaved[:usable].reshape(-1, self._channels).T)
        total = decoder.duration()
        if total > 0:
            self.progress.emit(min((buffer.startTime() + buffer.duration()) / 1000 / total, 1.0))

    def _on_finished(self) -> None:
        chunks, rate = self._chunks, self._rate
        self._release()
        if not chunks or rate <= 0:
            self.failed.emit("The file contains no decodable audio")
            return
        self.progress.emit(1.0)
        self.decoded.emit(AudioClip(np.concatenate(chunks, axis=1), rate))

    def _on_error(self, *_: object) -> None:
        decoder = self._decoder
        message = decoder.errorString() if decoder is not None else "decoder error"
        self._release()
        self.failed.emit(message or "The file could not be decoded")

    def _release(self) -> None:
        decoder, self._decoder = self._decoder, None
        if decoder is not None:
            decoder.bufferReady.disconnect(self._on_buffer)
            decoder.finished.disconnect(self._on_finished)
            decoder.error.disconnect(self._on_error)
            decoder.stop()
            decoder.deleteLater()


def decode_file(path: str | Path, timeout: float = 120.0) -> AudioClip:
    """Decode ``path`` and wait for the result. Needs a running ``QCoreApplication``.

    Prefer :class:`AudioDecoder` in a GUI, since this spins a nested event loop until done.
    """
    loop = QEventLoop()
    decoder = AudioDecoder()
    result: dict[str, object] = {}
    decoder.decoded.connect(lambda clip: (result.update(clip=clip), loop.quit()))
    decoder.failed.connect(lambda message: (result.update(error=message), loop.quit()))
    QTimer.singleShot(
        int(timeout * 1000), lambda: (result.setdefault("error", "timed out"), loop.quit())
    )
    decoder.decode(path)
    if decoder.is_running or not result:
        loop.exec()
    decoder.cancel()
    if "clip" not in result:
        raise DecodeError(str(result.get("error", "decoding failed")))
    return result["clip"]  # type: ignore[return-value]


def load_clip(path: str | Path) -> AudioClip:
    """Load any supported audio file: WAV directly, everything else through the decoder."""
    if Path(path).suffix.lower() == ".wav":
        return AudioClip.from_wav(path)
    return decode_file(path)
