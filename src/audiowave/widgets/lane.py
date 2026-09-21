"""LaneRenderer: paints one channel with a style and caches the result between playhead ticks."""

from __future__ import annotations

import math
from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPixmap

from audiowave.appearance import Appearance
from audiowave.core.peaks import Peaks

from .painters import PaintJob, WavePainter, get_painter


class LaneRenderer:
    """Renders one lane in two colours and clips them to the played / unplayed regions.

    While the data, size and appearance are unchanged the two colour layers are cached as pixmaps,
    so advancing the playhead costs two blits instead of a full repaint of every bar.
    """

    def __init__(self) -> None:
        self._key: tuple | None = None
        self._layers: tuple[QPixmap, QPixmap] | None = None

    def paint(
        self,
        painter: QPainter,
        rect: QRectF,
        peaks: Peaks,
        appearance: Appearance,
        progress: float,
        token: object | None = None,
    ) -> None:
        """Paint into ``rect``. ``token`` identifies ``peaks``; pass ``None`` to disable caching."""
        style = get_painter(appearance.style)
        resolved = style.resolve(appearance)
        if len(peaks) == 0 or rect.width() < 1 or rect.height() < 1:
            return

        if token is None:
            self._layers = self._key = None
            draw_unplayed = self._direct(style, rect, peaks, resolved, resolved.palette.unplayed)
            draw_played = self._direct(style, rect, peaks, resolved, resolved.palette.played)
        else:
            dpr = painter.device().devicePixelRatioF()
            key = (
                token,
                round(rect.width(), 2),
                round(rect.height(), 2),
                resolved,
                dpr,
            )
            if key != self._key:
                self._layers = (
                    self._render(style, rect, peaks, resolved, resolved.palette.unplayed, dpr),
                    self._render(style, rect, peaks, resolved, resolved.palette.played, dpr),
                )
                self._key = key
            unplayed_pm, played_pm = self._layers  # type: ignore[misc]
            draw_unplayed = lambda p: p.drawPixmap(rect.topLeft(), unplayed_pm)  # noqa: E731
            draw_played = lambda p: p.drawPixmap(rect.topLeft(), played_pm)  # noqa: E731

        self._composite(
            painter,
            rect,
            style.played_region(rect, progress),
            progress,
            draw_unplayed,
            draw_played,
        )

    # -- internals ------------------------------------------------------------------------------

    @staticmethod
    def _render(
        style: WavePainter,
        rect: QRectF,
        peaks: Peaks,
        appearance: Appearance,
        color: str,
        dpr: float,
    ) -> QPixmap:
        pixmap = QPixmap(math.ceil(rect.width() * dpr), math.ceil(rect.height() * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        style.paint(
            p,
            PaintJob(QRectF(0, 0, rect.width(), rect.height()), peaks, appearance),
            QColor(color),
        )
        p.end()
        return pixmap

    @staticmethod
    def _direct(
        style: WavePainter,
        rect: QRectF,
        peaks: Peaks,
        appearance: Appearance,
        color: str,
    ) -> Callable[[QPainter], None]:
        def draw(p: QPainter) -> None:
            p.save()
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            style.paint(p, PaintJob(rect, peaks, appearance), QColor(color))
            p.restore()

        return draw

    @staticmethod
    def _composite(
        painter: QPainter,
        rect: QRectF,
        region: QRectF | QPainterPath,
        progress: float,
        draw_unplayed: Callable[[QPainter], None],
        draw_played: Callable[[QPainter], None],
    ) -> None:
        painter.save()
        if progress >= 1.0:
            draw_played(painter)
        elif progress <= 0.0:
            draw_unplayed(painter)
        elif isinstance(region, QRectF):
            painter.setClipRect(
                QRectF(
                    region.right(),
                    rect.top(),
                    rect.right() - region.right(),
                    rect.height(),
                )
            )
            draw_unplayed(painter)
            painter.setClipRect(region)
            draw_played(painter)
        else:
            whole = QPainterPath()
            whole.addRect(rect)
            painter.setClipPath(whole.subtracted(region))
            draw_unplayed(painter)
            painter.setClipPath(region)
            draw_played(painter)
        painter.restore()
