"""StreamSender: a TCP server that broadcasts audio to every connected receiver."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QHostAddress, QTcpServer, QTcpSocket

from audiowave import AudioClip, AudioFormat, SampleFormat
from audiowave.core import decode_pcm, encode_pcm

from .protocol import encode_end, encode_frame, encode_hello, split_pcm

_BATCH = (
    25  # frames written per event-loop turn when sending a whole clip, so the UI stays responsive
)


class StreamSender(QObject):
    """Listens for receivers and sends them audio, live (:meth:`send_samples`) or whole (:meth:`send_clip`).

    Runs entirely on the Qt event loop: no threads and no locking. A receiver that connects while a
    stream is active is sent the format header first so it can decode what follows.
    """

    listeningChanged = Signal(bool)
    clientsChanged = Signal(int)
    frameSent = Signal(int, int, object)  # frame index, bytes, samples (channels, frames) float32
    sendFinished = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = QTcpServer(self)
        self._server.newConnection.connect(self._accept)
        self._clients: list[QTcpSocket] = []
        self._format: AudioFormat | None = None
        self._index = 0
        self._queue: list[bytes] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._drain_queue)

    # -- server ---------------------------------------------------------------------------------

    @property
    def is_listening(self) -> bool:
        return self._server.isListening()

    @property
    def port(self) -> int:
        return self._server.serverPort()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def listen(self, port: int, host: QHostAddress | None = None) -> bool:
        """Start accepting receivers. ``port=0`` picks a free one (see :attr:`port`)."""
        if self.is_listening:
            return True
        if not self._server.listen(host or QHostAddress(QHostAddress.SpecialAddress.Any), port):
            self.errorOccurred.emit(self._server.errorString())
            return False
        self.listeningChanged.emit(True)
        return True

    def stop(self) -> None:
        self._timer.stop()
        self._queue.clear()
        for client in list(self._clients):
            client.disconnectFromHost()
        self._clients.clear()
        self._server.close()
        self._format = None
        self.clientsChanged.emit(0)
        self.listeningChanged.emit(False)

    # -- sending --------------------------------------------------------------------------------

    def begin_stream(self, sample_rate: int, channels: int) -> None:
        """Announce the format to all receivers (and to any that join later)."""
        self._format = AudioFormat(sample_rate, channels, SampleFormat.S16)
        self._index = 0
        self._broadcast(encode_hello(sample_rate, channels))

    def send_samples(self, samples: np.ndarray) -> None:
        """Send a live ``(channels, frames)`` float chunk, split into ~20 ms frames."""
        if self._format is None:
            return
        for pcm in split_pcm(encode_pcm(samples, SampleFormat.S16), self._format):
            self._send_frame(pcm)

    def send_clip(self, clip: AudioClip) -> None:
        """Send a whole clip in paced batches, then an end marker."""
        self.begin_stream(clip.sample_rate, clip.channels)
        assert self._format is not None
        self._queue = split_pcm(clip.to_pcm(SampleFormat.S16), self._format)
        self._timer.start(0)

    def end_stream(self) -> None:
        if self._format is not None:
            self._broadcast(encode_end())
            self._format = None

    # -- internals ------------------------------------------------------------------------------

    def _accept(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            self._clients.append(socket)
            socket.disconnected.connect(
                self._on_client_disconnected
            )  # bound slot: auto-disconnected on destruction
            if self._format is not None:
                socket.write(encode_hello(self._format.sample_rate, self._format.channels))
            self.clientsChanged.emit(len(self._clients))

    def _on_client_disconnected(self) -> None:
        socket = self.sender()
        if socket in self._clients:
            self._clients.remove(socket)
            socket.deleteLater()
            self.clientsChanged.emit(len(self._clients))

    def _send_frame(self, pcm: bytes) -> None:
        self._broadcast(encode_frame(pcm))
        samples = decode_pcm(pcm, SampleFormat.S16, self._format.channels if self._format else 1)
        self.frameSent.emit(self._index, len(pcm), samples)
        self._index += 1

    def _broadcast(self, data: bytes) -> None:
        for client in self._clients:
            client.write(data)

    def _drain_queue(self) -> None:
        for _ in range(_BATCH):
            if not self._queue:
                break
            self._send_frame(self._queue.pop(0))
        if not self._queue:
            self._timer.stop()
            self.end_stream()
            self.sendFinished.emit()
