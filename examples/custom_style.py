"""Adding a waveform style: write one class, decorate it, and every widget can use it.

    python examples/custom_style.py

This "ticks" style draws a short vertical tick at each bucket's peak. Nothing else in the library
changes: the registry, the lane renderer's played/unplayed colouring and the caching all apply.
"""

import sys

import numpy as np
from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication

from audiowave import Appearance, AudioClip
from audiowave.widgets import PaintJob, WaveformView, WavePainter, register
from audiowave.widgets.painters.base import column_x, extents


@register
class Ticks(WavePainter):
    name = "ticks"
    label = "Ticks"
    uses_bar_shape = True  # the Width / Spacing sliders apply

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        up, _down = extents(job)  # honours gravity, scale and idle height for free
        mid = job.rect.center().y()
        painter.setPen(QPen(color, job.appearance.bar_width))
        for x, u in zip(column_x(job).tolist(), up.tolist(), strict=True):
            painter.drawLine(QPointF(x, mid - u), QPointF(x, mid - u + 3))


def main() -> int:
    app = QApplication(sys.argv)
    view = WaveformView()
    t = np.linspace(0, 4, 4 * 22050)
    sweep = np.sin(2 * np.pi * (200 + 300 * t) * t) * np.abs(np.sin(t * 2.2))  # a swelling chirp
    view.set_clip(AudioClip(sweep, 22050))
    view.set_appearance(Appearance(style="ticks"))
    view.set_position(1.5)
    view.resize(800, 220)
    view.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
