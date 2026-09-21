"""TakesView: a horizontal strip of recordings with mini waveforms."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from audiowave import Appearance, ClipPeaks, Peaks
from audiowave.widgets import get_painter
from audiowave.widgets.lane import LaneRenderer
from studio.models import Take, TakesModel
from studio.theme import get_theme

from .kit import IconButton, set_property


def format_duration(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:04.1f}"


class _MiniWave(QWidget):
    def __init__(self, take: Take, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._peaks = ClipPeaks(take.clip)
        self._cache: tuple[int, Peaks] | None = None
        self.current = False
        self.setFixedHeight(34)

    def paintEvent(self, _: QPaintEvent) -> None:
        t = get_theme()
        appearance = Appearance(
            style="bars",
            bar_width=1.5,
            bar_spacing=1.5,
            radius=0.5,
            scale=1.0,
            idle_height=1,
            palette=t.waveform.with_(
                played=t.accent if self.current else t.muted,
                unplayed=t.muted if self.current else t.line2,
            ),
        )
        style = get_painter("bars")
        n = style.buckets(self.width(), appearance)
        if self._cache is None or self._cache[0] != n:
            channels = self._peaks.query(0, self._peaks.duration, n)
            self._cache = (n, channels[0])
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        LaneRenderer().paint(
            p,
            QRectF(0, 0, self.width(), self.height()),
            self._cache[1],
            appearance,
            1.0 if self.current else 0.0,
        )
        p.end()


class TakeCard(QFrame):
    clicked = Signal(object)
    contextRequested = Signal(object, object)  # take, global position

    def __init__(self, take: Take, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.take = take
        self.setObjectName("take")
        self.setFixedSize(190, 96)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        col = QVBoxLayout(self)
        col.setContentsMargins(11, 8, 11, 8)
        col.setSpacing(5)
        top = QHBoxLayout()
        self._name = QLabel(take.name)
        self._name.setStyleSheet("font-weight: 600;")
        self._badge = QLabel("CURRENT")
        self._badge.setProperty("tag", True)
        self._badge.hide()
        top.addWidget(self._name)
        top.addStretch()
        top.addWidget(self._badge)
        self._wave = _MiniWave(take)
        bottom = QHBoxLayout()
        clip = take.clip
        left = QLabel(format_duration(clip.duration))
        right = QLabel(
            f"{clip.sample_rate / 1000:g}k · {'st' if clip.channels == 2 else 'mono' if clip.channels == 1 else str(clip.channels) + 'ch'}"
        )
        for label in (left, right):
            label.setObjectName("subtime")
        bottom.addWidget(left)
        bottom.addStretch()
        bottom.addWidget(right)
        col.addLayout(top)
        col.addWidget(self._wave)
        col.addLayout(bottom)

    def set_current(self, current: bool) -> None:
        set_property(self, "current", current)
        self._badge.setVisible(current)
        self._wave.current = current
        self._wave.update()

    def refresh_name(self) -> None:
        self._name.setText(self.take.name)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.take)
        elif event.button() == Qt.MouseButton.RightButton:
            self.contextRequested.emit(self.take, event.globalPosition().toPoint())


class _NewCard(QFrame):
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("take")
        self.setProperty("new", True)
        self.setFixedSize(190, 96)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon = IconButton("rec", kind="flat", size=24, icon_size=14, role="red")
        self._icon.setEnabled(False)
        label = QLabel("New recording")
        label.setObjectName("muted")
        row.addWidget(self._icon)
        row.addWidget(label)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.clicked.emit()


class TakesView(QScrollArea):
    """Shows every take of a :class:`TakesModel`, highlights the current one, and reports user intent."""

    newRecordingRequested = Signal()

    def __init__(self, takes: TakesModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._takes = takes
        self._cards: dict[Take, TakeCard] = {}
        self.setWidgetResizable(True)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setFixedHeight(112)
        host = QWidget()
        self._row = QHBoxLayout(host)
        self._row.setContentsMargins(0, 2, 0, 2)
        self._row.setSpacing(10)
        self._new = _NewCard()
        self._new.clicked.connect(self.newRecordingRequested)
        self._row.addWidget(self._new)
        self._row.addStretch()
        self.setWidget(host)

        takes.added.connect(self._add_card)
        takes.removed.connect(self._remove_card)
        takes.renamed.connect(lambda t: self._cards[t].refresh_name())
        takes.currentChanged.connect(self._sync_current)
        for take in takes:
            self._add_card(take)
        self._sync_current(takes.current)

    def _add_card(self, take: Take) -> None:
        card = TakeCard(take)
        card.clicked.connect(self._takes.set_current)
        card.contextRequested.connect(self._context_menu)
        self._cards[take] = card
        self._row.insertWidget(self._row.count() - 2, card)  # before the "new" card and the stretch

    def _remove_card(self, take: Take) -> None:
        card = self._cards.pop(take, None)
        if card:
            card.deleteLater()

    def _sync_current(self, current: Take | None) -> None:
        for take, card in self._cards.items():
            card.set_current(take is current)

    def _context_menu(self, take: Take, pos) -> None:
        menu = QMenu(self)
        menu.addAction("Rename…", lambda: self._rename(take))
        menu.addAction("Save as WAV…", lambda: self._save(take))
        menu.addSeparator()
        menu.addAction("Delete", lambda: self._takes.remove(take))
        menu.exec(pos)

    def _rename(self, take: Take) -> None:
        name, ok = QInputDialog.getText(self, "Rename take", "Name", text=take.name)
        if ok:
            self._takes.rename(take, name)

    def _save(self, take: Take) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save take", f"{take.name}.wav", "WAV audio (*.wav)"
        )
        if path:
            take.clip.to_wav(Path(path))
            take.path = Path(path)
