"""AudioRecorder: capture from an input device into an AudioClip, streaming chunks as they arrive."""

from __future__ import annotations

from enum import Enum

import numpy as np
from PySide6.QtCore import QIODevice, QObject, Signal
from PySide6.QtMultimedia import QAudio, QAudioDevice, QAudioFormat, QAudioSource, QMediaDevices

from audiowave.core.clip import AudioClip
from audiowave.core.format import AudioFormat, SampleFormat, decode_pcm

_QT_TO_SAMPLE = {
    QAudioFormat.SampleFormat.UInt8: SampleFormat.U8,
    QAudioFormat.SampleFormat.Int16: SampleFormat.S16,
    QAudioFormat.SampleFormat.Int32: SampleFormat.S32,
    QAudioFormat.SampleFormat.Float: SampleFormat.F32,
}


class RecorderState(Enum):
    STOPPED = "stopped"
    RECORDING = "recording"
    PAUSED = "paused"


class AudioRecorder(QObject):
    """Records until :meth:`stop`, which returns the finished clip.

    ``chunkReady`` fires for every block of audio the device delivers (a ``(channels, frames)``
    float array), which is what live waveforms and network senders subscribe to.
    """

    chunkReady = Signal(object)  # np.ndarray (channels, frames)
    levelChanged = Signal(object)  # list[float] peak per channel of the latest chunk
    elapsedChanged = Signal(float)  # seconds recorded so far
    stateChanged = Signal(object)  # RecorderState
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = RecorderState.STOPPED
        self._source: QAudioSource | None = None
        self._io: QIODevice | None = None
        self._format: AudioFormat | None = None
        self._sample_format = SampleFormat.S16
        self._chunks: list[np.ndarray] = []
        self._frames = 0

    @property
    def state(self) -> RecorderState:
        return self._state

    @property
    def format(self) -> AudioFormat | None:
        """The format actually being captured (may differ from the one requested)."""
        return self._format

    @property
    def elapsed(self) -> float:
        return self._frames / self._format.sample_rate if self._format else 0.0

    def start(self, sample_rate: int = 44100, channels: int = 1, device: QAudioDevice | None = None) -> bool:
        """Begin a new recording. Returns False (and emits ``errorOccurred``) if it cannot start."""
        if self._state is not RecorderState.STOPPED:
            return False
        device = device or QMediaDevices.defaultAudioInput()
        if device.isNull():
            self.errorOccurred.emit("No audio input device available")
            return False

        fmt = QAudioFormat()
        fmt.setSampleRate(sample_rate)
        fmt.setChannelCount(channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        if not device.isFormatSupported(fmt):
            fmt = device.preferredFormat()
        sample_format = _QT_TO_SAMPLE.get(fmt.sampleFormat())
        if sample_format is None:
            self.errorOccurred.emit("The input device uses an unsupported sample format")
            return False

        self._chunks, self._frames = [], 0
        self._sample_format = sample_format
        self._format = AudioFormat(fmt.sampleRate(), fmt.channelCount(), sample_format)

        self._source = QAudioSource(device, fmt, self)
        self._source.stateChanged.connect(self._on_source_state)
        self._io = self._source.start()
        if self._io is None:
            self.errorOccurred.emit("Could not open the input device (is microphone access allowed?)")
            self._reset()
            return False
        self._io.readyRead.connect(self._drain)
        self._set_state(RecorderState.RECORDING)
        return True

    def pause(self) -> None:
        if self._state is RecorderState.RECORDING and self._source is not None:
            self._drain()
            self._source.suspend()
            self._set_state(RecorderState.PAUSED)

    def resume(self) -> None:
        if self._state is RecorderState.PAUSED and self._source is not None:
            self._source.resume()
            self._set_state(RecorderState.RECORDING)

    def stop(self) -> AudioClip | None:
        """End the recording and return it (``None`` if nothing was captured)."""
        if self._state is RecorderState.STOPPED:
            return None
        self._drain()
        clip = self._finish()
        self._reset()
        self._set_state(RecorderState.STOPPED)
        return clip

    # -- internals ------------------------------------------------------------------------------

    def _finish(self) -> AudioClip | None:
        if not self._chunks or self._format is None:
            return None
        return AudioClip(np.concatenate(self._chunks, axis=1), self._format.sample_rate)

    def _reset(self) -> None:
        if self._source is not None:
            self._source.stateChanged.disconnect(self._on_source_state)
            self._source.stop()
            self._source.deleteLater()
        self._source = self._io = None

    def _drain(self) -> None:
        if self._io is None or self._format is None:
            return
        data = bytes(self._io.readAll())
        if not data:
            return
        chunk = decode_pcm(data, self._sample_format, self._format.channels)
        if chunk.shape[1] == 0:
            return
        self._chunks.append(chunk)
        self._frames += chunk.shape[1]
        self.chunkReady.emit(chunk)
        self.levelChanged.emit([float(np.abs(c).max()) for c in chunk])
        self.elapsedChanged.emit(self.elapsed)

    def _on_source_state(self, state: QAudio.State) -> None:
        if state == QAudio.State.StoppedState and self._source is not None:
            error = self._source.error()
            if error != QAudio.Error.NoError:
                self.errorOccurred.emit(f"Recording stopped: {error.name}")
                self.stop()

    def _set_state(self, state: RecorderState) -> None:
        if state is not self._state:
            self._state = state
            self.stateChanged.emit(state)
