"""TimelineView: the shared base of every time-scrolling widget.

It owns what a timeline needs regardless of what is drawn inside it: a viewport, a playhead, a loop
region, markers, the ruler, and the mouse/wheel interaction (seek, loop drag, zoom, pan). Subclasses
only implement :meth:`paint_content`.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QEnterEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QWheelEvent,
)
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Palette

from .annotations import Loop, Marker
from .ruler import format_time, nice_step, paint_ruler, ticks
from .viewport import Viewport

_EDGE_GRAB_PX = 6
_MIN_LOOP_SECONDS = 0.05


class _Drag(Enum):
    NONE = auto()
    SEEK = auto()
    NEW_LOOP = auto()
    LOOP_START = auto()
    LOOP_END = auto()


class TimelineView(QWidget):
    """Base widget: ruler on top, subclass content below, overlays (loop, markers, playhead) over it."""

    seekRequested = Signal(float)
    loopChanged = Signal(object)  # Loop | None
    markerClicked = Signal(float)

    RULER_HEIGHT = 28

    def __init__(self, viewport: Viewport | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.viewport = viewport if viewport is not None else Viewport(self)
        self.viewport.changed.connect(self._on_viewport_changed)

        self._palette = Palette()
        self._position = 0.0
        self._loop: Loop | None = None
        self._markers: list[Marker] = []
        self._follow = False
        self._show_ruler = True

        self._drag = _Drag.NONE
        self._drag_anchor = 0.0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)

    # -- public state ---------------------------------------------------------------------------

    @property
    def theme(self) -> Palette:
        return self._palette

    def set_theme(self, palette: Palette) -> None:
        if palette != self._palette:
            self._palette = palette
            self.update()

    @property
    def position(self) -> float:
        return self._position

    def set_position(self, seconds: float) -> None:
        """Move the playhead. Scrolls the viewport when following and the user is not dragging."""
        seconds = min(max(seconds, 0.0), self.viewport.duration or seconds)
        if seconds == self._position:
            return
        self._position = seconds
        if self._follow and self._drag is _Drag.NONE:
            self.viewport.ensure_visible(seconds)
        self.update()

    @property
    def loop(self) -> Loop | None:
        return self._loop

    def set_loop(self, loop: Loop | None) -> None:
        if loop != self._loop:
            self._loop = loop
            self.update()

    @property
    def markers(self) -> list[Marker]:
        return list(self._markers)

    def set_markers(self, markers: list[Marker]) -> None:
        self._markers = sorted(markers, key=lambda m: m.time)
        self.update()

    @property
    def follow(self) -> bool:
        return self._follow

    def set_follow(self, follow: bool) -> None:
        self._follow = follow

    def set_ruler_visible(self, visible: bool) -> None:
        self._show_ruler = visible
        self.update()

    # -- geometry -------------------------------------------------------------------------------

    def ruler_rect(self) -> QRectF:
        return QRectF(0, 0, self.width(), self.RULER_HEIGHT if self._show_ruler else 0)

    def content_rect(self) -> QRectF:
        top = self.ruler_rect().height()
        return QRectF(0, top, self.width(), max(self.height() - top, 0))

    def time_to_x(self, t: float) -> float:
        return self.viewport.fraction(t) * self.width()

    def x_to_time(self, x: float) -> float:
        t = self.viewport.start + x / max(self.width(), 1) * self.viewport.span
        return min(max(t, 0.0), self.viewport.duration)

    def major_tick_times(self) -> list[float]:
        step = nice_step(self.viewport.span, self.width())
        return [t for t, major in ticks(self.viewport.start, self.viewport.end, step) if major]

    # -- hooks for subclasses -------------------------------------------------------------------

    def paint_content(self, painter: QPainter, rect: QRectF) -> None:  # pragma: no cover - abstract hook
        """Draw the view's own content inside ``rect`` (below the ruler)."""

    def paint_playhead_marks(self, painter: QPainter, x: float) -> None:
        """Optional extras drawn on the playhead line, e.g. a dot per channel lane."""

    def on_viewport_changed(self) -> None:
        """Called after the viewport changed. Override to invalidate caches."""

    def _on_viewport_changed(self) -> None:
        self.on_viewport_changed()
        self.update()

    # -- painting -------------------------------------------------------------------------------

    def paintEvent(self, _: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(self._palette.background))

        if self.viewport.duration > 0:
            if self._show_ruler:
                self._paint_ruler(painter)
            content = self.content_rect()
            painter.save()
            painter.setClipRect(content)
            self.paint_content(painter, content)
            painter.restore()
            self._paint_overlays(painter)
        painter.end()

    def _paint_ruler(self, painter: QPainter) -> None:
        font = self.font()
        font.setPointSizeF(max(font.pointSizeF() - 1.5, 7.0))
        font.setFamilies([*font.families(), "Menlo", "Consolas", "monospace"])
        paint_ruler(painter, self.ruler_rect(), self.viewport.start, self.viewport.end, self._palette, font)

    def _paint_overlays(self, painter: QPainter) -> None:
        top, bottom = self.ruler_rect().height(), float(self.height())
        painter.save()
        painter.setClipRect(QRectF(0, 0, self.width(), self.height()))

        if self._loop is not None:
            self._paint_loop(painter, top, bottom)
        for marker in self._markers:
            if self.viewport.start <= marker.time <= self.viewport.end:
                self._paint_marker(painter, marker, top, bottom)

        if self.viewport.start <= self._position <= self.viewport.end:
            x = self.time_to_x(self._position)
            painter.setPen(QPen(QColor(self._palette.playhead), 1.5))
            painter.drawLine(QPointF(x, top), QPointF(x, bottom))
            self.paint_playhead_marks(painter, x)
            if self._show_ruler:
                self._paint_time_flag(painter, x)
        painter.restore()

    def _paint_loop(self, painter: QPainter, top: float, bottom: float) -> None:
        assert self._loop is not None
        x0, x1 = self.time_to_x(self._loop.start), self.time_to_x(self._loop.end)
        colour = QColor(self._palette.loop)
        tint = QColor(colour)
        tint.setAlpha(28)
        painter.fillRect(QRectF(x0, top, x1 - x0, bottom - top), tint)
        painter.fillRect(QRectF(x0, 0, x1 - x0, 3), colour)
        painter.setPen(QPen(colour, 2))
        for x in (x0, x1):
            painter.drawLine(QPointF(x, 0), QPointF(x, bottom))

    def _paint_marker(self, painter: QPainter, marker: Marker, top: float, bottom: float) -> None:
        colour = QColor(self._palette.marker)
        x = self.time_to_x(marker.time)
        faint = QColor(colour)
        faint.setAlpha(90)
        painter.setPen(QPen(faint, 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(x, top), QPointF(x, bottom))
        if not self._show_ruler:
            return
        base = self.RULER_HEIGHT
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(colour)
        painter.drawPolygon([QPointF(x, base - 14), QPointF(x + 8, base - 10), QPointF(x, base - 6)])
        painter.fillRect(QRectF(x - 1, base - 14, 1.5, 14), colour)
        if marker.label:
            painter.setPen(colour)
            painter.drawText(QPointF(x + 11, base - 7), marker.label)

    def _paint_time_flag(self, painter: QPainter, x: float) -> None:
        step = nice_step(self.viewport.span, self.width())
        text = format_time(self._position, min(step, 0.1))
        metrics = painter.fontMetrics()
        w, h = metrics.horizontalAdvance(text) + 14, 18
        left = min(max(x - w / 2, 0), self.width() - w)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self._palette.played))
        painter.drawRoundedRect(QRectF(left, 3, w, h), 5, 5)
        painter.setPen(QColor(self._palette.background))
        painter.drawText(QRectF(left, 3, w, h), int(Qt.AlignmentFlag.AlignCenter), text)

    # -- interaction ----------------------------------------------------------------------------

    def _hit_loop_edge(self, x: float) -> _Drag:
        if self._loop is None:
            return _Drag.NONE
        if abs(x - self.time_to_x(self._loop.start)) <= _EDGE_GRAB_PX:
            return _Drag.LOOP_START
        if abs(x - self.time_to_x(self._loop.end)) <= _EDGE_GRAB_PX:
            return _Drag.LOOP_END
        return _Drag.NONE

    def _marker_at(self, x: float, y: float) -> Marker | None:
        if not self._show_ruler or y > self.RULER_HEIGHT:
            return None
        for marker in self._markers:
            if abs(x - self.time_to_x(marker.time)) <= 8:
                return marker
        return None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self.viewport.duration <= 0:
            return
        pos = event.position()
        t = self.x_to_time(pos.x())

        if (marker := self._marker_at(pos.x(), pos.y())) is not None:
            self.markerClicked.emit(marker.time)
            self.seekRequested.emit(marker.time)
            return

        edge = self._hit_loop_edge(pos.x())
        in_ruler = self._show_ruler and pos.y() < self.RULER_HEIGHT
        if edge is not _Drag.NONE:
            self._drag = edge
        elif in_ruler or event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self._drag, self._drag_anchor = _Drag.NEW_LOOP, t
        else:
            self._drag = _Drag.SEEK
            self.seekRequested.emit(t)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        pos = event.position()
        t = self.x_to_time(pos.x())
        if self._drag is _Drag.SEEK:
            self.seekRequested.emit(t)
        elif self._drag is _Drag.NEW_LOOP:
            if abs(t - self._drag_anchor) >= _MIN_LOOP_SECONDS:
                self._set_loop_from_drag(Loop(self._drag_anchor, t))
        elif self._drag is _Drag.LOOP_START and self._loop:
            self._set_loop_from_drag(Loop(min(t, self._loop.end - _MIN_LOOP_SECONDS), self._loop.end))
        elif self._drag is _Drag.LOOP_END and self._loop:
            self._set_loop_from_drag(Loop(self._loop.start, max(t, self._loop.start + _MIN_LOOP_SECONDS)))
        else:
            near_edge = self._hit_loop_edge(pos.x()) is not _Drag.NONE
            on_marker = self._marker_at(pos.x(), pos.y()) is not None
            self.setCursor(
                Qt.CursorShape.SizeHorCursor
                if near_edge
                else Qt.CursorShape.PointingHandCursor
                if on_marker
                else Qt.CursorShape.ArrowCursor
            )

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag is _Drag.NEW_LOOP and (self._loop is None or self._loop.length < _MIN_LOOP_SECONDS):
            # A click on the ruler that never became a drag is just a seek.
            self.seekRequested.emit(self._drag_anchor)
        self._drag = _Drag.NONE

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._loop is not None and self._loop.contains(self.x_to_time(event.position().x())):
            self._loop = None
            self.loopChanged.emit(None)
            self.update()

    def enterEvent(self, event: QEnterEvent) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().enterEvent(event)

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta()
        zoom_modifier = event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier)
        if zoom_modifier and delta.y():
            self.viewport.zoom(1.2 ** (delta.y() / 120), self.x_to_time(event.position().x()))
        else:
            amount = delta.x() or delta.y()
            self.viewport.pan(-amount / 120 * self.viewport.span * 0.1)
        event.accept()

    def _set_loop_from_drag(self, loop: Loop) -> None:
        loop = Loop(max(loop.start, 0.0), min(loop.end, self.viewport.duration))
        if loop != self._loop:
            self._loop = loop
            self.loopChanged.emit(loop)
            self.update()
