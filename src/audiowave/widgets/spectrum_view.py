"""SpectrumView: a live frequency analyser (log-spaced bars with peak hold)."""

from __future__ import annotations

import time

import numpy as np
from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Palette
from audiowave.core.analysis import band_levels

FLOOR_DB = -90.0
_FALL_DB_PER_S = 45.0
_HOLD_SECONDS = 0.9
_LABELS = ((100, "100"), (1000, "1k"), (10000, "10k"))


class SpectrumView(QWidget):
    """Feed it the most recent audio (a mono window) with :meth:`feed`; it shows 48 log-spaced bands.

    Bars rise instantly and fall smoothly; a tick marks each band's recent peak. The widget animates
    itself while there is anything to animate and then stops its timer.
    """

    def __init__(self, bands: int = 48, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bands = bands
        self._palette = Palette()
        self._centres = np.geomspace(30, 16000, bands)
        self._shown = np.full(bands, FLOOR_DB)
        self._hold = np.full(bands, FLOOR_DB)
        self._hold_age = np.zeros(bands)
        self._last_tick = time.monotonic()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self.setMinimumSize(160, 100)

    def set_theme(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    @property
    def levels(self) -> np.ndarray:
        """Currently displayed level of each band in dBFS."""
        return self._shown.copy()

    @property
    def centres(self) -> np.ndarray:
        return self._centres.copy()

    def feed(self, samples: np.ndarray, sample_rate: int) -> None:
        """Analyse the tail of ``samples`` (mono) and update the display."""
        if samples.size == 0:
            return
        self._centres, levels = band_levels(samples, sample_rate, self._bands)
        rising = levels > self._shown
        self._shown = np.where(rising, levels, self._shown)
        new_peak = levels >= self._hold
        self._hold = np.where(new_peak, levels, self._hold)
        self._hold_age = np.where(new_peak, 0.0, self._hold_age)
        self._start_animating()
        self.update()

    def clear(self) -> None:
        self._shown[:] = FLOOR_DB
        self._hold[:] = FLOOR_DB
        self._timer.stop()
        self.update()

    def _start_animating(self) -> None:
        if not self._timer.isActive():
            self._last_tick = time.monotonic()
            self._timer.start()

    def _advance(self) -> None:
        now = time.monotonic()
        dt, self._last_tick = now - self._last_tick, now
        self._shown = np.maximum(self._shown - _FALL_DB_PER_S * dt, FLOOR_DB)
        self._hold_age += dt
        falling = self._hold_age > _HOLD_SECONDS
        self._hold = np.where(
            falling, np.maximum(self._hold - _FALL_DB_PER_S * 0.6 * dt, self._shown), self._hold
        )
        if (self._shown <= FLOOR_DB).all() and (self._hold <= FLOOR_DB).all():
            self._timer.stop()
        self.update()

    def _y(self, db: float, top: float, height: float) -> float:
        return top + height * (1 - min(max((db - FLOOR_DB) / -FLOOR_DB, 0.0), 1.0))

    def paintEvent(self, _: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = self._palette
        p.fillRect(self.rect(), QColor(pal.background))
        left, bottom_margin = 34.0, 20.0
        plot = QRectF(left, 8, self.width() - left - 8, self.height() - bottom_margin - 8)

        font = self.font()
        font.setPointSizeF(max(font.pointSizeF() - 2, 7.0))
        p.setFont(font)
        grid = QColor(pal.grid)
        for db in (-20, -40, -60, -80):
            y = self._y(db, plot.top(), plot.height())
            p.setPen(QPen(grid, 1))
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            p.setPen(QColor(pal.text))
            p.drawText(
                QRectF(0, y - 8, left - 6, 16),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                str(db),
            )

        n = self._bands
        slot = plot.width() / n
        bar_w = max(slot - 2, 1.0)
        floor_y = plot.bottom()
        p.setPen(Qt.PenStyle.NoPen)
        base, hot = QColor(pal.played), QColor(pal.marker)
        for i in range(n):
            x = plot.left() + i * slot + 1
            y = self._y(self._shown[i], plot.top(), plot.height())
            level = (self._shown[i] - FLOOR_DB) / -FLOOR_DB
            colour = QColor(base)
            if level > 0.85:  # the top of the range warms towards the accent, like a meter
                colour = QColor(hot)
            colour.setAlphaF(0.55 + 0.45 * level)
            p.setBrush(colour)
            if floor_y - y > 0.5:
                p.drawRoundedRect(QRectF(x, y, bar_w, floor_y - y), 1.5, 1.5)
            if self._hold[i] > FLOOR_DB + 1:
                p.setBrush(QColor(pal.playhead))
                p.drawRect(
                    QRectF(x, self._y(self._hold[i], plot.top(), plot.height()) - 1, bar_w, 1.6)
                )

        p.setPen(QColor(pal.text))
        for hz, text in _LABELS:
            if self._centres[0] < hz < self._centres[-1]:
                i = int(np.argmin(np.abs(self._centres - hz)))
                cx = plot.left() + (i + 0.5) * slot
                p.drawText(
                    QRectF(cx - 20, plot.bottom() + 3, 40, 14),
                    int(Qt.AlignmentFlag.AlignCenter),
                    text,
                )
        p.end()
