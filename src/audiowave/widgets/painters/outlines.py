"""Silhouette styles built from a single QPainterPath: Envelope, Smooth line and Stairs."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen

from audiowave.appearance import Appearance

from .base import PaintJob, WavePainter, column_x, extents
from .registry import register

_ENVELOPE_PX_PER_BUCKET = 2.0


def _edges(job: PaintJob, xs: np.ndarray) -> tuple[list[QPointF], list[QPointF]]:
    """Top and bottom outline points for the given x positions."""
    up, down = extents(job)
    mid = job.rect.center().y()
    top = [QPointF(x, mid - u) for x, u in zip(xs.tolist(), up.tolist(), strict=True)]
    bottom = [QPointF(x, mid + d) for x, d in zip(xs.tolist(), down.tolist(), strict=True)]
    return top, bottom


def _polygon(top: list[QPointF], bottom: list[QPointF]) -> QPainterPath:
    path = QPainterPath()
    if not top:
        return path
    path.moveTo(top[0])
    for point in top[1:]:
        path.lineTo(point)
    for point in reversed(bottom):
        path.lineTo(point)
    path.closeSubpath()
    return path


def _smooth(points: list[QPointF]) -> QPainterPath:
    """Curve through ``points`` using each midpoint as an anchor and each point as a control."""
    path = QPainterPath()
    if not points:
        return path
    path.moveTo(points[0])
    for prev, cur in zip(points, points[1:], strict=False):
        path.quadTo(prev, (prev + cur) / 2)
    path.lineTo(points[-1])
    return path


class _Outline(WavePainter):
    """Shared behaviour: the shape spans the lane instead of using bar width/spacing."""

    def buckets(self, width: float, appearance: Appearance) -> int:
        return max(int(width / _ENVELOPE_PX_PER_BUCKET), 1)

    @staticmethod
    def _xs(job: PaintJob) -> np.ndarray:
        return np.linspace(job.rect.left(), job.rect.right(), max(len(job.peaks), 2))[: len(job.peaks)]


@register
class Envelope(_Outline):
    name = "env"
    label = "Envelope"

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        top, bottom = _edges(job, self._xs(job))
        painter.fillPath(_polygon(top, bottom), color)


@register
class SmoothLine(_Outline):
    """Two spline curves through the peaks and troughs, over a faint fill."""

    name = "line"
    label = "Line"

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        top, bottom = _edges(job, self._xs(job))
        tint = QColor(color)
        tint.setAlphaF(color.alphaF() * 0.15)
        painter.fillPath(_polygon(top, bottom), tint)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(color, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(_smooth(top))
        painter.drawPath(_smooth(bottom))
        painter.restore()


@register
class Stairs(WavePainter):
    """A stepped silhouette that keeps every bucket visible, honest about resolution."""

    name = "stairs"
    label = "Stairs"
    uses_bar_shape = True

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        a = job.appearance
        step = a.bar_width + a.bar_spacing
        up, down = extents(job)
        xs = column_x(job).tolist()
        mid = job.rect.center().y()

        path = QPainterPath()
        if xs:
            path.moveTo(xs[0], mid - up[0])
            for x, u in zip(xs, up.tolist(), strict=True):
                path.lineTo(x, mid - u)
                path.lineTo(x + step, mid - u)
            for x, d in zip(reversed(xs), reversed(down.tolist()), strict=True):
                path.lineTo(x + step, mid + d)
                path.lineTo(x, mid + d)
            path.closeSubpath()
        painter.fillPath(path, color)
