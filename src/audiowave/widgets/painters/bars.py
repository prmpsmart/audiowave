"""Bar-based styles: Bars, Capsule, Hairline, RMS + Peak and Ground."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath

from audiowave.appearance import Appearance, Gravity

from .base import PaintJob, WavePainter, column_x, extents, half_height
from .registry import register


def draw_rects(painter: QPainter, rects: list[QRectF], radius: float) -> None:
    """Fill ``rects`` with the current brush, rounded if ``radius`` is visible (>= half a pixel)."""
    painter.setPen(Qt.PenStyle.NoPen)
    if radius < 0.5:
        painter.drawRects(rects)
        return
    path = QPainterPath()
    for rect in rects:
        path.addRoundedRect(rect, radius, radius)
    painter.drawPath(path)


def symmetric_rects(xs, up, down, mid: float, width: float) -> list[QRectF]:
    return [
        QRectF(x, mid - u, width, u + d)
        for x, u, d in zip(xs.tolist(), up.tolist(), down.tolist(), strict=True)
    ]


@register
class Bars(WavePainter):
    name = "bars"
    label = "Bars"
    uses_bar_shape = True

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        a = job.appearance
        up, down = extents(job)
        painter.setBrush(color)
        rects = symmetric_rects(column_x(job), up, down, job.rect.center().y(), a.bar_width)
        draw_rects(painter, rects, min(a.radius, a.bar_width / 2))


@register
class Capsule(Bars):
    """Bars whose ends are fully rounded."""

    name = "capsule"
    label = "Capsule"

    def resolve(self, appearance: Appearance) -> Appearance:
        return appearance.with_(radius=appearance.bar_width / 2)


@register
class Hairline(Bars):
    """One-pixel needles: dense and light, good for long recordings."""

    name = "hair"
    label = "Hairline"

    def resolve(self, appearance: Appearance) -> Appearance:
        return appearance.with_(bar_width=1.0, radius=0.0)


@register
class RmsPeak(WavePainter):
    """A bright RMS core inside a dim peak halo: shows perceived loudness as well as spikes."""

    name = "rms"
    label = "RMS + Peak"
    uses_bar_shape = True
    uses_gravity = False

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        a = job.appearance
        half, mid = half_height(job), job.rect.center().y()
        xs, floor = column_x(job), a.idle_height / 2
        outer_up, outer_down = extents(
            PaintJob(job.rect, job.peaks, a.with_(gravity=Gravity.MIN_MAX))
        )
        core = (job.peaks.rms.astype("float64") * half).clip(min=floor)
        radius = min(a.radius, a.bar_width / 2)

        painter.save()
        painter.setBrush(color)
        painter.setOpacity(painter.opacity() * 0.32)
        draw_rects(painter, symmetric_rects(xs, outer_up, outer_down, mid, a.bar_width), radius)
        painter.setOpacity(painter.opacity() / 0.32)
        draw_rects(painter, symmetric_rects(xs, core, core, mid, a.bar_width), radius)
        painter.restore()


@register
class Ground(WavePainter):
    """Bars stand on a baseline with a fading reflection beneath, like a "now playing" card."""

    name = "ground"
    label = "Ground"
    uses_bar_shape = True
    uses_gravity = False

    BASE = 0.68  # baseline position as a fraction of lane height

    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        a, rect = job.appearance, job.rect
        base = rect.top() + rect.height() * self.BASE
        rise = rect.height() * self.BASE * a.scale
        reflect = rect.bottom() - base
        heights = (job.peaks.amplitude.astype("float64") * rise).clip(min=a.idle_height)
        xs = column_x(job).tolist()
        radius = min(a.radius, a.bar_width / 2)

        painter.setBrush(color)
        draw_rects(
            painter,
            [
                QRectF(x, base - h, a.bar_width, h)
                for x, h in zip(xs, heights.tolist(), strict=True)
            ],
            radius,
        )

        faded = QColor(color)
        faded.setAlphaF(color.alphaF() * 0.4)
        clear = QColor(color)
        clear.setAlpha(0)
        gradient = QLinearGradient(QPointF(0, base), QPointF(0, base + reflect))
        gradient.setColorAt(0, faded)
        gradient.setColorAt(1, clear)
        painter.setBrush(gradient)
        draw_rects(
            painter,
            [
                QRectF(x, base + 1, a.bar_width, min(h * 0.6, reflect))
                for x, h in zip(xs, heights.tolist(), strict=True)
            ],
            0,
        )
