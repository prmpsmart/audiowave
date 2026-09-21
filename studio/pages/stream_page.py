"""Stream page: send audio to another studio over TCP, or receive it. The successor of the Mimi Wave demo.

Sender  = the old "server": Start/Stop server, stream the microphone live or send a take.
Receiver = the old "client": Connect/Disconnect, then play what arrived.
"""

from __future__ import annotations

from PySide6.QtCore import QModelIndex, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from audiowave import LivePeaks
from audiowave.audio import RecorderState, request_microphone
from audiowave.widgets import LiveWaveformView
from studio.models import Take
from studio.session import Session
from studio.stream import PORT_RANGE, FrameLogModel, StreamReceiver, StreamSender
from studio.stream.log_model import LEVEL_ROLE
from studio.stream.protocol import FRAME_MS
from studio.theme import get_theme
from studio.widgets import Segmented, chip, set_property

DEFAULT_PORT = 7421
VISIBLE_SECONDS = 8.0


class _LevelDelegate(QStyledItemDelegate):
    """Draws the Level column as a small bar."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        if index.column() != 3:
            return super().paint(painter, option, index)
        level = float(index.data(LEVEL_ROLE) or 0)
        rect = QRectF(option.rect).adjusted(6, 0, -6, 0)
        bar = QRectF(
            rect.left(),
            rect.center().y() - 2.5,
            max(rect.width() * min(level, 1.0), 2),
            5,
        )
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(get_theme().accent))
        painter.setOpacity(0.75)
        painter.drawRoundedRect(bar, 2.5, 2.5)
        painter.restore()


class StreamPage(QWidget):
    playRequested = Signal(object)  # Take

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = session
        self.sender = StreamSender(self)
        self.receiver = StreamReceiver(self)
        self.log = FrameLogModel(parent=self)
        self._live: LivePeaks | None = None
        self._clock = 0.0  # seconds of audio seen on this link, for the Time column
        self._bytes = 0
        self._rate = 44100
        self._received_count = 0
        self._mic_streaming = False

        col = QVBoxLayout(self)
        col.setContentsMargins(22, 16, 22, 18)
        col.setSpacing(12)
        col.addLayout(self._title_row())
        col.addWidget(self._session_card())
        col.addWidget(self._lane_card(), 1)
        col.addWidget(self._frames_card(), 1)

        self._wire()
        self._set_role("sender")
        self._render_state()

    # -- construction ---------------------------------------------------------------------------

    def _title_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel("Stream")
        title.setObjectName("h1")
        self.role = Segmented([("sender", "Sender"), ("receiver", "Receiver")])
        self.role.setFixedWidth(210)
        self.status = QLabel()
        row.addWidget(title)
        row.addStretch()
        row.addWidget(self.status)
        row.addSpacing(8)
        row.addWidget(self.role)
        return row

    def _session_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(18)

        self.host_box, self.host = self._field("Host", QLineEdit("localhost"))
        self.port = QSpinBox()
        self.port.setRange(*PORT_RANGE)
        self.port.setValue(DEFAULT_PORT)
        self.port.setFixedWidth(96)
        port_box, _ = self._field("Port", self.port)
        hint = QLabel(f"Allowed range {PORT_RANGE[0]} – {PORT_RANGE[1]}")
        hint.setObjectName("dim")
        port_box.layout().addWidget(hint)

        self.main_button = QPushButton()
        self.main_button.setProperty("primary", True)
        self.mic_button = QPushButton("Stream microphone")
        self.send_button = QPushButton("Send current take")
        row.addWidget(self.host_box)
        row.addWidget(port_box)
        row.addStretch(1)
        for b in (self.mic_button, self.send_button, self.main_button):
            row.addWidget(b)
        return card

    @staticmethod
    def _field(label: str, editor: QWidget) -> tuple[QWidget, QWidget]:
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(5)
        caption = QLabel(label.upper())
        caption.setObjectName("eyebrow")
        col.addWidget(caption)
        col.addWidget(editor)
        return box, editor

    def _lane_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 12, 16, 12)
        col.setSpacing(10)
        top = QHBoxLayout()
        self.lane_title = QLabel()
        self.lane_title.setObjectName("h2")
        self.frames_chip = chip()
        self.format_chip = chip()
        top.addWidget(self.lane_title)
        top.addStretch()
        top.addWidget(self.format_chip)
        top.addWidget(self.frames_chip)
        col.addLayout(top)
        well = QFrame()
        well.setObjectName("well")
        inner = QVBoxLayout(well)
        inner.setContentsMargins(6, 6, 6, 6)
        self.live_view = LiveWaveformView()
        self.live_view.setMinimumHeight(150)
        inner.addWidget(self.live_view)
        col.addWidget(well, 1)
        bottom = QHBoxLayout()
        self.play_button = QPushButton("Play recording")
        self.play_button.setProperty("primary", True)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("ghost", True)
        bottom.addStretch()
        bottom.addWidget(self.clear_button)
        bottom.addWidget(self.play_button)
        col.addLayout(bottom)
        return card

    def _frames_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        col = QVBoxLayout(card)
        col.setContentsMargins(16, 12, 16, 12)
        head = QHBoxLayout()
        title = QLabel("Frames")
        title.setObjectName("h2")
        self.frames_note = QLabel()
        self.frames_note.setObjectName("muted")
        head.addWidget(title)
        head.addStretch()
        head.addWidget(self.frames_note)
        col.addLayout(head)
        self.table = QTableView()
        self.table.setModel(self.log)
        self.table.setItemDelegate(_LevelDelegate(self.table))
        self.table.verticalHeader().hide()
        self.table.setShowGrid(False)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setSelectionMode(QTableView.SelectionMode.NoSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        for i, w in enumerate((90, 110, 110)):
            self.table.setColumnWidth(i, w)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        col.addWidget(self.table, 1)
        return card

    # -- wiring ---------------------------------------------------------------------------------

    def _wire(self) -> None:
        self.role.currentChanged.connect(self._set_role)
        self.main_button.clicked.connect(self._on_main_button)
        self.mic_button.clicked.connect(self._toggle_mic)
        self.send_button.clicked.connect(self._send_take)
        self.play_button.clicked.connect(self._play_received)
        self.clear_button.clicked.connect(self._clear)

        s, r = self.sender, self.receiver
        s.listeningChanged.connect(self._render_state)
        s.clientsChanged.connect(self._render_state)
        s.errorOccurred.connect(lambda e: self._s.message.emit(e, True))
        s.frameSent.connect(self._on_frame)
        s.sendFinished.connect(self._render_state)

        r.connectedChanged.connect(self._render_state)
        r.errorOccurred.connect(lambda e: self._s.message.emit(e, True))
        r.formatReceived.connect(self._on_format)
        r.frameReceived.connect(self._on_frame)
        r.streamEnded.connect(self._render_state)

        rec = self._s.recorder
        rec.chunkReady.connect(self._on_mic_chunk)
        rec.stateChanged.connect(self._render_state)
        self._s.appearance.changed.connect(self.apply_appearance)
        self.apply_appearance()

    # -- role & state ---------------------------------------------------------------------------

    @property
    def is_sender(self) -> bool:
        return self.role.current == "sender"

    def _set_role(self, _: str = "") -> None:
        sender = self.is_sender
        self.host_box.setVisible(not sender)
        self.mic_button.setVisible(sender)
        self.send_button.setVisible(sender)
        self.play_button.setVisible(not sender)
        self.lane_title.setText("Sending" if sender else "Receiving")
        self._reset_lane()
        self._render_state()

    def _render_state(self, *_: object) -> None:
        sender, r, s = self.is_sender, self.receiver, self.sender
        rec_state = self._s.recorder.state
        if sender:
            self.main_button.setText("Stop server" if s.is_listening else "Start server")
            self.port.setEnabled(not s.is_listening)
            if s.is_listening:
                n = s.client_count
                self._pill(f"Listening on :{s.port} · {n} client{'s' if n != 1 else ''}", "ok")
            else:
                self._pill("Server stopped", "idle")
            self._mic_streaming = self._mic_streaming and rec_state is not RecorderState.STOPPED
            self.mic_button.setText(
                "Stop microphone" if self._mic_streaming else "Stream microphone"
            )
            self.mic_button.setEnabled(
                s.is_listening and (self._mic_streaming or rec_state is RecorderState.STOPPED)
            )
            self.send_button.setEnabled(
                s.is_listening and s.client_count > 0 and self._s.clip is not None
            )
        else:
            self.main_button.setText("Disconnect" if r.is_connected else "Connect")
            self.host.setEnabled(not r.is_connected)
            self.port.setEnabled(not r.is_connected)
            self._pill(
                "Connected" if r.is_connected else "Not connected",
                "ok" if r.is_connected else "idle",
            )
            self.play_button.setEnabled(r.frame_count > 0)
        self.clear_button.setEnabled(self.log.rowCount() > 0)
        self.frames_note.setText(f"{FRAME_MS} ms per frame")

    def _pill(self, text: str, state: str) -> None:
        self.status.setText(text)
        set_property(self.status, "state", state)

    # -- actions --------------------------------------------------------------------------------

    def _on_main_button(self) -> None:
        if self.is_sender:
            if self.sender.is_listening:
                self._stop_mic()
                self.sender.stop()
            else:
                self.sender.listen(self.port.value())
        elif self.receiver.is_connected:
            self.receiver.disconnect_from()
        else:
            host = self.host.text().strip()
            if not host:
                self._s.message.emit("Enter the sender's address first.", True)
                return
            self._reset_lane()
            self.receiver.connect_to(host, self.port.value())

    def _toggle_mic(self) -> None:
        if self._mic_streaming:
            self._stop_mic()
        else:
            request_microphone(self, self._start_mic)

    def _start_mic(self, granted: bool) -> None:
        if not granted:
            self._s.message.emit("Microphone access was denied.", True)
            return
        device = self._s.input_device.native if self._s.input_device else None
        rec = self._s.recorder
        if not rec.start(22050, 1, device) or rec.format is None:
            return
        self._reset_lane()
        self._begin_live(rec.format.sample_rate, rec.format.channels)
        self.sender.begin_stream(rec.format.sample_rate, rec.format.channels)
        self._mic_streaming = True
        self._render_state()

    def _stop_mic(self) -> None:
        if self._mic_streaming:
            self._s.recorder.stop()
            self.sender.end_stream()
            self._mic_streaming = False
            self._render_state()

    def _on_mic_chunk(self, samples) -> None:
        if self._mic_streaming:
            self.sender.send_samples(samples)

    def _send_take(self) -> None:
        clip = self._s.clip
        if clip is None:
            return
        self._reset_lane()
        self._begin_live(clip.sample_rate, clip.channels)
        self.sender.send_clip(clip)

    def _play_received(self) -> None:
        clip = self.receiver.clip()
        if clip is None:
            return
        self._received_count += 1
        take: Take = self._s.takes.add(clip, name=f"Received {self._received_count}")
        self.playRequested.emit(take)

    def _clear(self) -> None:
        self.receiver.clear()
        self._reset_lane()
        self._render_state()

    # -- data -> view ---------------------------------------------------------------------------

    def _reset_lane(self) -> None:
        self.log.clear()
        self._clock, self._bytes = 0.0, 0
        self._live = None
        self.live_view.set_source(None)
        self.format_chip.setText("")
        self.frames_chip.setText("")

    def _begin_live(self, sample_rate: int, channels: int) -> None:
        self._rate = sample_rate
        spb = max(
            int(sample_rate * VISIBLE_SECONDS / max(self.live_view.buckets_for_width(), 1)),
            64,
        )
        self._live = LivePeaks(channels, spb)
        self.live_view.set_source(self._live)
        self.format_chip.setText(f"{sample_rate / 1000:g} kHz · {channels} ch")

    def _on_format(self, fmt) -> None:
        if not self.is_sender:
            self._reset_lane()
            self._begin_live(fmt.sample_rate, fmt.channels)

    def _on_frame(self, index: int, size: int, samples) -> None:
        if self._live is None:
            return
        self._live.append(samples)
        self.live_view.refresh()
        self._clock += samples.shape[1] / self._rate
        self._bytes += size
        self.log.add(index, size, self._clock, float(abs(samples).max()))
        self.frames_chip.setText(f"{index + 1:,} F | {self._bytes / 1_000_000:.2f} MB")
        self._render_state()

    def apply_appearance(self) -> None:
        self.live_view.set_appearance(self._s.appearance.appearance(0).with_(show_grid=False))

    def refresh_theme(self) -> None:
        self.apply_appearance()
        self._render_state()
