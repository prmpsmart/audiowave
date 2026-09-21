"""VectorscopeView: left against right as an XY plot of the audio around the playhead."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Palette
from audiowave.core.analysis import correlation, stereo_xy
from audiowave.core.clip import AudioClip

_BATCHES = 4  # older points are drawn in fainter batches to suggest a trail


class VectorscopeView(QWidget):
    """A mono signal plots as a vertical line, a wide stereo image as a cloud.

    The scope shows the ``window`` seconds *ending* at the position, so it moves with playback.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clip: AudioClip | None = None
        self._palette = Palette()
        self._position = 0.0
        self._window = 0.05
        self._gain = 1.0
        self.setMinimumSize(120, 120)

    def set_theme(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        peak = clip.peak() if clip is not None else 0.0
        self._gain = 0.9 / peak if peak > 1e-6 else 1.0  # fill the graticule regardless of loudness
        self._position = 0.0
        self.update()

    def set_position(self, seconds: float) -> None:
        self._position = seconds
        self.update()

    def set_window(self, seconds: float) -> None:
        self._window = max(seconds, 0.005)
        self.update()

    def correlation(self) -> float:
        """Stereo correlation of the current window (+1 mono, -1 out of phase)."""
        left, right = self._window_samples()
        return correlation(left, right) if left.size else 0.0

    def _window_samples(self) -> tuple[np.ndarray, np.ndarray]:
        if self._clip is None:
            empty = np.zeros(0, np.float32)
            return empty, empty
        rate = self._clip.sample_rate
        end = min(max(int(self._position * rate), 0), self._clip.frames)
        start = max(end - int(self._window * rate), 0)
        left = self._clip.channel(0)[start:end]
        right = self._clip.channel(1)[start:end] if self._clip.channels > 1 else left
        return left, right

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self._palette
        painter.fillRect(self.rect(), QColor(palette.background))
        centre = QPointF(self.width() / 2, self.height() / 2)
        radius = max(min(self.width(), self.height()) / 2 - 12, 10.0)
        self._paint_graticule(painter, centre, radius)

        left, right = self._window_samples()
        if left.size:
            x, y = stereo_xy(left * self._gain, right * self._gain)
            xs, ys = centre.x() + x * radius, centre.y() - y * radius
            chunk = max(len(xs) // _BATCHES, 1)
            painter.setPen(QPen(QColor(palette.played), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            for b in range(_BATCHES):
                part = slice(b * chunk, None if b == _BATCHES - 1 else (b + 1) * chunk)
                painter.setOpacity(0.18 + 0.82 * (b + 1) / _BATCHES)
                painter.drawPoints(QPolygonF([QPointF(px, py) for px, py in zip(xs[part].tolist(), ys[part].tolist(), strict=True)]))
            painter.setOpacity(1.0)

        painter.setPen(QColor(palette.text))
        painter.drawText(8, self.height() - 8, f"corr {self.correlation():+.2f}")
        painter.end()

    def _paint_graticule(self, painter: QPainter, c: QPointF, r: float) -> None:
        grid = QColor(self._palette.grid).lighter(130)
        painter.setPen(QPen(grid, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(c, r, r)
        painter.drawEllipse(c, r / 2, r / 2)
        painter.drawPolygon([QPointF(c.x(), c.y() - r), QPointF(c.x() + r, c.y()), QPointF(c.x(), c.y() + r), QPointF(c.x() - r, c.y())])
        painter.drawLine(QPointF(c.x(), c.y() - r), QPointF(c.x(), c.y() + r))
        painter.drawLine(QPointF(c.x() - r, c.y()), QPointF(c.x() + r, c.y()))
        painter.setPen(QColor(self._palette.text))
        painter.drawText(QPointF(c.x() - 4, c.y() - r - 2), "M")
        painter.drawText(QPointF(c.x() - r - 10, c.y() - r * 0.7), "L")
        painter.drawText(QPointF(c.x() + r + 2, c.y() - r * 0.7), "R")
