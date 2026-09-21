"""LevelMeter: a segmented peak meter with hold and smooth fall-off."""

from __future__ import annotations

import time

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget

from audiowave.core.analysis import to_db

FLOOR_DB = -60.0
_FALL_DB_PER_S = 36.0
_HOLD_SECONDS = 1.2


class LevelMeter(QWidget):
    """Shows a linear peak level (0..1) on a dB scale.

    Call :meth:`set_level` whenever a new peak is known; the meter animates the fall and the
    peak-hold tick itself and stops its timer once everything has settled.
    """

    def __init__(
        self,
        orientation: Qt.Orientation = Qt.Orientation.Vertical,
        segments: int = 26,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._orientation = orientation
        self._segments = segments
        self._shown = FLOOR_DB
        self._hold = FLOOR_DB
        self._hold_age = 0.0
        self._last_tick = time.monotonic()
        self._colors = ("#ffb238", "#ff8a1f", "#ff4b3a")
        self._off = "#1c1e19"
        self._tick = "#ece6d6"
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)

    @property
    def level_db(self) -> float:
        return self._shown

    def set_colors(self, normal: str, warm: str, hot: str, off: str, tick: str) -> None:
        self._colors, self._off, self._tick = (normal, warm, hot), off, tick
        self.update()

    def set_level(self, peak: float) -> None:
        """Feed a linear peak (1.0 = full scale)."""
        db = max(float(to_db(peak, FLOOR_DB)), FLOOR_DB)
        if db >= self._shown:
            self._shown = db
        if db >= self._hold:
            self._hold, self._hold_age = db, 0.0
        if not self._timer.isActive():
            self._last_tick = time.monotonic()
            self._timer.start()
        self.update()

    def reset(self) -> None:
        self._shown = self._hold = FLOOR_DB
        self._timer.stop()
        self.update()

    def _advance(self) -> None:
        now = time.monotonic()
        dt, self._last_tick = now - self._last_tick, now
        self._shown = max(self._shown - _FALL_DB_PER_S * dt, FLOOR_DB)
        self._hold_age += dt
        if self._hold_age > _HOLD_SECONDS:
            self._hold = max(self._hold - _FALL_DB_PER_S * 0.6 * dt, self._shown, FLOOR_DB)
        if self._shown <= FLOOR_DB and self._hold <= FLOOR_DB:
            self._timer.stop()
        self.update()

    def _fraction(self, db: float) -> float:
        return min(max((db - FLOOR_DB) / -FLOOR_DB, 0.0), 1.0)

    def _segment_color(self, fraction: float) -> QColor:
        normal, warm, hot = self._colors
        return QColor(hot if fraction > 0.95 else warm if fraction > 0.8 else normal)

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        vertical = self._orientation is Qt.Orientation.Vertical
        length = self.height() if vertical else self.width()
        thickness = self.width() if vertical else self.height()
        cell = length / self._segments
        lit = self._fraction(self._shown)
        hold = self._fraction(self._hold)

        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(self._segments):
            f = i / self._segments
            painter.setBrush(self._segment_color(f) if f < lit else QColor(self._off))
            a, b = i * cell + 0.6, cell - 1.6
            rect = QRectF(0, length - a - b, thickness, b) if vertical else QRectF(a, 0, b, thickness)
            painter.drawRoundedRect(rect, 1.5, 1.5)
        if hold > 0:
            painter.setBrush(QColor(self._tick))
            pos = hold * length
            painter.drawRect(QRectF(0, length - pos, thickness, 1.5) if vertical else QRectF(pos, 0, 1.5, thickness))
        painter.end()
