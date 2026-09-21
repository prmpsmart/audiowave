"""StreamReceiver: connects to a StreamSender and collects the audio it sends."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from audiowave import AudioClip, AudioFormat, SampleFormat
from audiowave.core import decode_pcm

from .protocol import FrameDecoder, MessageType, ProtocolError, parse_hello


class StreamReceiver(QObject):
    """Receives frames and keeps them, so the finished stream can be turned into a clip at any moment."""

    connectedChanged = Signal(bool)
    formatReceived = Signal(object)  # AudioFormat
    frameReceived = Signal(int, int, object)  # index, bytes, samples (channels, frames) float32
    streamEnded = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._socket = QTcpSocket(self)
        # Bound slots, not lambdas: Qt drops these connections when this object is destroyed, so a
        # socket torn down with its parent can never call back into a half-destroyed receiver.
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.errorOccurred.connect(self._on_socket_error)
        self._decoder = FrameDecoder()
        self._format: AudioFormat | None = None
        self._chunks: list[np.ndarray] = []
        self._bytes = 0

    # -- connection -----------------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._socket.state() == QAbstractSocket.SocketState.ConnectedState

    def connect_to(self, host: str, port: int) -> None:
        self.clear()
        self._socket.connectToHost(host, port)

    def disconnect_from(self) -> None:
        self._socket.abort()
        self.connectedChanged.emit(False)

    # -- data -----------------------------------------------------------------------------------

    @property
    def format(self) -> AudioFormat | None:
        return self._format

    @property
    def frame_count(self) -> int:
        return len(self._chunks)

    @property
    def byte_count(self) -> int:
        return self._bytes

    def clip(self) -> AudioClip | None:
        """Everything received so far, or ``None`` if nothing usable has arrived."""
        if not self._chunks or self._format is None:
            return None
        return AudioClip(np.concatenate(self._chunks, axis=1), self._format.sample_rate)

    def clear(self) -> None:
        self._decoder.reset()
        self._format, self._chunks, self._bytes = None, [], 0

    # -- internals ------------------------------------------------------------------------------

    def _on_connected(self) -> None:
        self.connectedChanged.emit(True)

    def _on_disconnected(self) -> None:
        self.connectedChanged.emit(False)

    def _on_ready_read(self) -> None:
        try:
            messages = self._decoder.feed(bytes(self._socket.readAll()))
            for message in messages:
                self._handle(message.type, message.payload)
        except ProtocolError as error:
            self.errorOccurred.emit(f"Protocol error: {error}")
            self._socket.abort()
            self.connectedChanged.emit(False)

    def _handle(self, kind: MessageType, payload: bytes) -> None:
        if kind is MessageType.HELLO:
            self._format = parse_hello(payload)
            self._chunks, self._bytes = [], 0
            self.formatReceived.emit(self._format)
        elif kind is MessageType.FRAME and self._format is not None:
            samples = decode_pcm(payload, SampleFormat.S16, self._format.channels)
            if samples.shape[1]:
                self._chunks.append(samples)
                self._bytes += len(payload)
                self.frameReceived.emit(len(self._chunks) - 1, len(payload), samples)
        elif kind is MessageType.END:
            self.streamEnded.emit()

    def _on_socket_error(self, _: QAbstractSocket.SocketError) -> None:
        self.errorOccurred.emit(self._socket.errorString())
