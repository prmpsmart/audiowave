"""SpectrogramView: a frequency-over-time heat map that scrolls and zooms with the waveform."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Palette
from audiowave.core.analysis import Spectrogram, spectrogram
from audiowave.core.clip import AudioClip

from .timeline import TimelineView
from .viewport import Viewport

_FREQ_STEPS = (100, 200, 500, 1000, 2000, 5000, 10000)


def heat_lut(palette: Palette) -> np.ndarray:
    """256-entry ARGB lookup: background -> dim accent -> accent -> near white."""
    stops = [
        (0.0, QColor(palette.background)),
        (0.30, QColor(palette.played).darker(420)),
        (0.62, QColor(palette.played).darker(150)),
        (0.85, QColor(palette.played)),
        (1.0, QColor(palette.played).lighter(190)),
    ]
    positions = np.array([s[0] for s in stops])
    channels = np.array([[c.red(), c.green(), c.blue()] for _, c in stops], np.float64)
    x = np.linspace(0, 1, 256)
    rgb = np.stack([np.interp(x, positions, channels[:, i]) for i in range(3)], axis=1).astype(
        np.uint32
    )
    return (0xFF << 24) | (rgb[:, 0] << 16) | (rgb[:, 1] << 8) | rgb[:, 2]


class SpectrogramView(TimelineView):
    """Shows one channel's spectrogram over the shared viewport's time range."""

    def __init__(self, viewport: Viewport | None = None, parent: QWidget | None = None) -> None:
        super().__init__(viewport, parent)
        self._spec: Spectrogram | None = None
        self._clip: AudioClip | None = None
        self._image: QImage | None = None
        self._channel = 0
        self._range_db = (-90.0, -10.0)
        self.setMinimumHeight(self.RULER_HEIGHT + 60)

    def set_clip(self, clip: AudioClip | None, channel: int = 0) -> None:
        """Analyse ``channel`` of ``clip``. The viewport is only reset if its duration differs."""
        self._clip, self._channel = clip, channel
        self._spec = (
            spectrogram(clip.channel(channel), clip.sample_rate) if clip is not None else None
        )
        self._image = None
        if clip is not None and abs(self.viewport.duration - clip.duration) > 1e-6:
            self.viewport.set_duration(clip.duration)
        self.update()

    def set_range_db(self, low: float, high: float) -> None:
        """Contrast window: levels at or below ``low`` are darkest, at or above ``high`` brightest."""
        self._range_db = (low, max(high, low + 1))
        self._image = None
        self.update()

    def set_theme(self, palette: Palette) -> None:
        if palette != self.theme:
            self._image = None
        super().set_theme(palette)

    @property
    def spectrogram(self) -> Spectrogram | None:
        return self._spec

    def _build_image(self) -> QImage:
        assert self._spec is not None
        low, high = self._range_db
        idx = np.clip((self._spec.magnitude_db - low) / (high - low) * 255, 0, 255).astype(np.uint8)
        pixels = np.ascontiguousarray(heat_lut(self.theme)[idx[::-1]])  # highest frequency on top
        h, w = pixels.shape
        return QImage(pixels.data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()

    def paint_content(self, painter: QPainter, rect: QRectF) -> None:
        if self._spec is None:
            return
        if self._image is None:
            self._image = self._build_image()
        spec = self._spec
        rate = spec.sample_rate

        def column(t: float) -> float:
            return (t * rate - spec.n_fft / 2) / spec.hop

        c0, c1 = column(self.viewport.start), column(self.viewport.end)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(
            rect, self._image, QRectF(c0, 0, max(c1 - c0, 1e-3), self._image.height())
        )
        self._paint_frequency_axis(painter, rect, spec)

    def _paint_frequency_axis(self, painter: QPainter, rect: QRectF, spec: Spectrogram) -> None:
        painter.save()
        font = self.font()
        font.setPointSizeF(max(font.pointSizeF() - 1.5, 7.0))
        painter.setFont(font)
        last_label_y = float("inf")
        for hz in (h for h in _FREQ_STEPS if h < spec.nyquist * 0.98):
            y = rect.bottom() - hz / spec.nyquist * rect.height()
            painter.setPen(QColor(255, 255, 255, 34))
            painter.drawLine(rect.left(), y, rect.right(), y)
            if (
                last_label_y - y >= painter.fontMetrics().height()
            ):  # labels closer than a line would collide
                painter.setPen(QColor(255, 255, 255, 170))
                painter.drawText(
                    rect.left() + 6,
                    int(y) - 3,
                    f"{hz // 1000}k" if hz >= 1000 else str(hz),
                )
                last_label_y = y
        painter.setPen(Qt.PenStyle.NoPen)
        painter.restore()
