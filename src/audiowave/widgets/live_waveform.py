"""LiveWaveformView: a waveform that grows while audio is being recorded or received."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Appearance
from audiowave.core.live import LivePeaks

from .lane import LaneRenderer
from .painters import get_painter

LANE_GAP = 6


class LiveWaveformView(QWidget):
    """Draws the tail of a :class:`LivePeaks`: fills left to right, then scrolls.

    Everything drawn is "played" colour; the empty space ahead of the head is a dashed midline.
    Call :meth:`refresh` after appending to the source.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._live: LivePeaks | None = None
        self._appearance = Appearance(show_grid=False)
        self._renderers: list[LaneRenderer] = []
        self._head_color: QColor | None = None
        self.setMinimumHeight(60)

    def set_source(self, live: LivePeaks | None) -> None:
        self._live = live
        self._renderers = [LaneRenderer() for _ in range(live.channels if live else 0)]
        self.update()

    def set_appearance(self, appearance: Appearance) -> None:
        self._appearance = appearance
        self.update()

    def set_head_color(self, color: QColor | str | None) -> None:
        self._head_color = QColor(color) if color is not None else None
        self.update()

    def refresh(self) -> None:
        self.update()

    def buckets_for_width(self) -> int:
        """How many envelope buckets one full-width lane holds, for sizing a ``LivePeaks``."""
        style = get_painter(self._appearance.style)
        return style.buckets(max(self.width(), 1), style.resolve(self._appearance))

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        a = self._appearance
        painter.fillRect(self.rect(), QColor(a.palette.background))
        if self._live is None or not self._renderers:
            painter.end()
            return

        style = get_painter(a.style)
        wanted = style.buckets(self.width(), style.resolve(a))
        n = self._live.channels
        lane_h = (self.height() - LANE_GAP * (n - 1)) / n
        head_color = self._head_color or QColor(a.palette.playhead)

        for channel, peaks in enumerate(self._live.tail(wanted)):
            top = channel * (lane_h + LANE_GAP)
            lane = QRectF(0, top, self.width(), lane_h)
            filled = self.width() * min(len(peaks) / wanted, 1.0)
            mid = lane.center().y()

            painter.setPen(QPen(QColor(a.palette.grid).lighter(150), 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(filled, mid), QPointF(self.width(), mid))
            if len(peaks):
                self._renderers[channel].paint(painter, QRectF(0, top + 4, filled, lane_h - 8), peaks, a, 1.0)

            painter.setPen(QPen(head_color, 1.5))
            painter.drawLine(QPointF(filled, top + 6), QPointF(filled, top + lane_h - 6))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(head_color)
            painter.drawEllipse(QPointF(filled, mid), 4.5, 4.5)
        painter.end()
