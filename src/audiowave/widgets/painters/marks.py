"""Styles built from discrete marks rather than bars or outlines: Dots and Radial."""

from __future__ import annotations

import math

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from .base import PaintJob, WavePainter, column_x, extents
from .registry import register


@register
class Dots(WavePainter):
    """Stacked dots per column, like an LED level meter, fading towards the tips."""

    name = "dots"
    label = "Dots"
    uses_bar_shape = True

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        a = job.appearance
        diameter = a.bar_width
        pitch = diameter + 1.5
        up, down = extents(job)
        rows_up, rows_down = (up // pitch).astype(int), (down // pitch).astype(int)
        top_row = int(max(rows_up.max(initial=0), rows_down.max(initial=0)))
        cx = column_x(job) + diameter / 2
        mid = job.rect.center().y()
        r = diameter / 2

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        base_opacity = painter.opacity()
        for k in range(0, top_row + 1):
            path = QPainterPath()
            for i in np.flatnonzero(rows_up >= k).tolist():
                path.addEllipse(QPointF(cx[i], mid - k * pitch), r, r)
            if k:
                for i in np.flatnonzero(rows_down >= k).tolist():
                    path.addEllipse(QPointF(cx[i], mid + k * pitch), r, r)
            painter.setOpacity(base_opacity * (1.0 - 0.55 * k / max(top_row, 1)))
            painter.drawPath(path)
        painter.restore()


@register
class Radial(WavePainter):
    """Bars around a ring; the played part sweeps clockwise from twelve o'clock."""

    name = "radial"
    label = "Radial"
    uses_bar_shape = True
    uses_gravity = False
    full_span = True

    SPOKES = 120
    INNER = 0.36  # inner radius as a fraction of the outer radius

    def buckets(self, width: float, appearance) -> int:
        return self.SPOKES

    def _geometry(self, rect: QRectF) -> tuple[QPointF, float]:
        return rect.center(), max(min(rect.width(), rect.height()) / 2 - 4, 1.0)

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        a = job.appearance
        centre, outer = self._geometry(job.rect)
        inner = outer * self.INNER
        n = len(job.peaks)
        amp = np.clip(job.peaks.amplitude, 0.03, 1.0) * a.scale
        angles = np.arange(n) / max(n, 1) * 2 * math.pi - math.pi / 2
        lines = [
            QLineF(
                centre.x() + math.cos(t) * inner,
                centre.y() + math.sin(t) * inner,
                centre.x() + math.cos(t) * (inner + m * (outer - inner)),
                centre.y() + math.sin(t) * (inner + m * (outer - inner)),
            )
            for t, m in zip(angles.tolist(), amp.tolist(), strict=True)
        ]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(
            QPen(color, max(a.bar_width * 0.8, 1.6), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        painter.drawLines(lines)
        ring = QColor(color)
        ring.setAlphaF(color.alphaF() * 0.25)
        painter.setPen(QPen(ring, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(centre, inner - 5, inner - 5)
        painter.restore()

    def played_region(self, rect: QRectF, progress: float) -> QRectF | QPainterPath:
        progress = min(max(progress, 0.0), 1.0)
        if progress >= 1.0:
            return QRectF(rect)
        centre, _ = self._geometry(rect)
        reach = math.hypot(rect.width(), rect.height())
        pie = QPainterPath()
        pie.moveTo(centre)
        pie.arcTo(
            QRectF(centre.x() - reach, centre.y() - reach, reach * 2, reach * 2),
            90.0,
            -360.0 * progress,
        )
        pie.closeSubpath()
        return pie
