"""OverviewView: the whole clip in miniature with a draggable window onto the main view."""

from __future__ import annotations

from enum import Enum, auto

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Appearance
from audiowave.core.clip import AudioClip
from audiowave.core.peaks import ClipPeaks, Peaks

from audiowave.core.annotations import Loop
from .lane import LaneRenderer
from .viewport import Viewport

_HANDLE_PX = 7


class _Grab(Enum):
    NONE = auto()
    MOVE = auto()
    LEFT = auto()
    RIGHT = auto()


class OverviewView(QWidget):
    """Draws the entire clip and the part of it the shared :class:`Viewport` currently shows.

    Drag inside the window to scroll, drag its edges to zoom, click outside to jump there.
    """

    seekRequested = Signal(float)

    def __init__(self, viewport: Viewport, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewport = viewport
        self.viewport.changed.connect(self.update)
        self._appearance = Appearance(style="hair", bar_width=1, bar_spacing=1, scale=1.0, show_midline=False)
        self._peaks: ClipPeaks | None = None
        self._renderer = LaneRenderer()
        self._cached: Peaks | None = None
        self._cached_width = 0
        self._position = 0.0
        self._loop: Loop | None = None
        self._grab = _Grab.NONE
        self._grab_offset = 0.0
        self.setMinimumHeight(40)
        self.setMouseTracking(True)

    def set_clip(self, clip: AudioClip | None, peaks: ClipPeaks | None = None) -> None:
        """Show ``clip``. Pass an existing ``ClipPeaks`` to avoid recomputing it."""
        self._peaks = peaks if peaks is not None else (ClipPeaks(clip) if clip is not None else None)
        self._cached = None
        self._position = 0.0
        self.update()

    def set_appearance(self, appearance: Appearance) -> None:
        self._appearance = appearance.with_(style="hair", bar_width=1, bar_spacing=1, scale=1.0, show_midline=False)
        self._cached = None
        self.update()

    def set_position(self, seconds: float) -> None:
        self._position = seconds
        self.update()

    def set_loop(self, loop: Loop | None) -> None:
        self._loop = loop
        self.update()

    # -- geometry -------------------------------------------------------------------------------

    def _x(self, t: float) -> float:
        d = self.viewport.duration
        return t / d * self.width() if d > 0 else 0.0

    def _t(self, x: float) -> float:
        return min(max(x / max(self.width(), 1) * self.viewport.duration, 0.0), self.viewport.duration)

    def _window(self) -> QRectF:
        return QRectF(self._x(self.viewport.start), 0, self._x(self.viewport.span), self.height())

    # -- painting -------------------------------------------------------------------------------

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self._appearance.palette
        painter.fillRect(self.rect(), QColor(palette.background))
        if self._peaks is None or self.viewport.duration <= 0:
            painter.end()
            return

        lane = QRectF(0, 4, self.width(), self.height() - 8)
        if self._cached is None or self._cached_width != self.width():
            merged = self._peaks.query(0, self.viewport.duration, max(self.width() // 2, 1))
            self._cached = self._mix(merged)
            self._cached_width = self.width()
        self._renderer.paint(
            painter, lane, self._cached, self._appearance, self._position / self.viewport.duration, token=("ov", self.width())
        )

        window = self._window()
        shade = QColor(palette.background)
        shade.setAlpha(150)
        painter.fillRect(QRectF(0, 0, window.left(), self.height()), shade)
        painter.fillRect(QRectF(window.right(), 0, self.width() - window.right(), self.height()), shade)

        accent = QColor(palette.played)
        painter.setPen(QPen(accent, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(window.adjusted(0.75, 0.75, -0.75, -0.75))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent)
        for x in (window.left(), window.right()):
            painter.drawRoundedRect(QRectF(x - 2.5, self.height() / 2 - 9, 5, 18), 2.5, 2.5)

        if self._loop is not None:
            painter.fillRect(
                QRectF(self._x(self._loop.start), self.height() - 3, self._x(self._loop.length), 3), QColor(palette.loop)
            )
        painter.setPen(QPen(QColor(palette.playhead), 1.5))
        painter.drawLine(QPointF(self._x(self._position), 0), QPointF(self._x(self._position), self.height()))
        painter.end()

    @staticmethod
    def _mix(channels: list[Peaks]) -> Peaks:
        """One combined envelope for the overview: the extremes across channels."""
        return Peaks(
            np.min([c.minimum for c in channels], axis=0),
            np.max([c.maximum for c in channels], axis=0),
            np.max([c.rms for c in channels], axis=0),
        )

    # -- interaction ----------------------------------------------------------------------------

    def _hit(self, x: float) -> _Grab:
        window = self._window()
        if abs(x - window.left()) <= _HANDLE_PX:
            return _Grab.LEFT
        if abs(x - window.right()) <= _HANDLE_PX:
            return _Grab.RIGHT
        return _Grab.MOVE if window.left() < x < window.right() else _Grab.NONE

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.viewport.duration <= 0:
            return
        x = event.position().x()
        self._grab = self._hit(x)
        if self._grab is _Grab.NONE:  # click outside: centre the window there and keep dragging it
            centre = self._t(x)
            self.viewport.set_range(centre - self.viewport.span / 2, centre + self.viewport.span / 2)
            self._grab = _Grab.MOVE
        self._grab_offset = self._t(x) - self.viewport.start

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        x = event.position().x()
        t = self._t(x)
        if self._grab is _Grab.MOVE:
            start = t - self._grab_offset
            self.viewport.set_range(start, start + self.viewport.span)
        elif self._grab is _Grab.LEFT:
            self.viewport.set_range(min(t, self.viewport.end - Viewport.MIN_SPAN), self.viewport.end)
        elif self._grab is _Grab.RIGHT:
            self.viewport.set_range(self.viewport.start, max(t, self.viewport.start + Viewport.MIN_SPAN))
        else:
            hit = self._hit(x)
            self.setCursor(
                Qt.CursorShape.SizeHorCursor
                if hit in (_Grab.LEFT, _Grab.RIGHT)
                else Qt.CursorShape.OpenHandCursor
                if hit is _Grab.MOVE
                else Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._grab = _Grab.NONE

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.seekRequested.emit(self._t(event.position().x()))
