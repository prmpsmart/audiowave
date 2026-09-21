"""WaveformView: a zoomable, seekable multi-channel waveform."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from audiowave.appearance import Appearance
from audiowave.core.clip import AudioClip
from audiowave.core.peaks import ClipPeaks, Peaks

from .lane import LaneRenderer
from .painters import get_painter
from .timeline import TimelineView
from .viewport import Viewport

LANE_GAP = 6


def layout_lanes(width: float, height: float, channels: int, top: float, gap: float = LANE_GAP) -> list[QRectF]:
    """Stack ``channels`` equal lanes in ``height`` below ``top``. Shared with widgets that must line up with them."""
    if channels <= 0:
        return []
    lane_h = (height - top - gap * (channels - 1)) / channels
    return [QRectF(0, top + i * (lane_h + gap), width, lane_h) for i in range(channels)]


class WaveformView(TimelineView):
    """One stacked lane per channel, each painted with its own :class:`Appearance`.

    Feed it a clip with :meth:`set_clip` and a playhead with :meth:`set_position`; it reports user
    intent through ``seekRequested`` and ``loopChanged`` and never touches audio playback itself.
    """

    def __init__(self, viewport: Viewport | None = None, parent: QWidget | None = None) -> None:
        super().__init__(viewport, parent)
        self._clip: AudioClip | None = None
        self._peaks: ClipPeaks | None = None
        self._appearances: list[Appearance] = [Appearance()]
        self._renderers: list[LaneRenderer] = []
        self._peak_cache: dict[tuple, Peaks] = {}
        self._token = 0
        self._auto_gain = False
        self.setMinimumHeight(self.RULER_HEIGHT + 60)

    # -- data -----------------------------------------------------------------------------------

    @property
    def clip(self) -> AudioClip | None:
        return self._clip

    @property
    def clip_peaks(self) -> ClipPeaks | None:
        """The envelope index, so sibling views (e.g. an overview) can reuse it instead of rebuilding."""
        return self._peaks

    def set_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self._peaks = ClipPeaks(clip) if clip is not None else None
        self._renderers = [LaneRenderer() for _ in range(clip.channels if clip else 0)]
        self._position = 0.0
        self._invalidate()
        self.viewport.set_duration(clip.duration if clip else 0.0)
        self.update()

    @property
    def auto_gain(self) -> bool:
        return self._auto_gain

    def set_auto_gain(self, enabled: bool) -> None:
        """Stretch the display so the loudest sample of the clip reaches full height (audio is unchanged)."""
        if enabled != self._auto_gain:
            self._auto_gain = enabled
            self._invalidate()
            self.update()

    # -- appearance -----------------------------------------------------------------------------

    def appearance(self, channel: int = 0) -> Appearance:
        return self._appearances[min(channel, len(self._appearances) - 1)]

    def set_appearance(self, appearance: Appearance, channel: int | None = None) -> None:
        """Apply to every channel, or only to ``channel``."""
        if channel is None:
            self._appearances = [appearance]
        else:
            while len(self._appearances) <= channel:
                self._appearances.append(self._appearances[-1])
            self._appearances[channel] = appearance
        if channel in (None, 0):
            self.set_theme(appearance.palette)
        self._invalidate()
        self.update()

    def _channel_appearance(self, channel: int) -> Appearance:
        return self._appearances[min(channel, len(self._appearances) - 1)]

    # -- geometry -------------------------------------------------------------------------------

    def lane_rects(self) -> list[QRectF]:
        """Rectangles of the channel lanes, top to bottom."""
        n = self._clip.channels if self._clip else 0
        return layout_lanes(self.width(), self.height(), n, self.ruler_rect().height())

    # -- caching --------------------------------------------------------------------------------

    def on_viewport_changed(self) -> None:
        self._invalidate()

    def _invalidate(self) -> None:
        self._peak_cache.clear()
        self._token += 1

    def _lane_peaks(self, channel: int, buckets: int) -> Peaks:
        key = (channel, buckets)
        peaks = self._peak_cache.get(key)
        if peaks is None:
            assert self._peaks is not None
            peaks = self._peaks.pyramids[channel].query(
                round(self.viewport.start * self._peaks.sample_rate),
                round(self.viewport.end * self._peaks.sample_rate),
                buckets,
            )
            self._peak_cache[key] = peaks = self._apply_gain(peaks)
        return peaks

    def _apply_gain(self, peaks: Peaks) -> Peaks:
        peak = self._clip.peak() if (self._auto_gain and self._clip) else 0.0
        if peak <= 1e-6:
            return peaks
        gain = np.float32(1.0 / peak)
        return Peaks(
            np.clip(peaks.minimum * gain, -1, 1),
            np.clip(peaks.maximum * gain, -1, 1),
            np.clip(peaks.rms * gain, 0, 1),
        )

    # -- painting -------------------------------------------------------------------------------

    def paint_content(self, painter: QPainter, rect: QRectF) -> None:
        if self._clip is None:
            return
        progress = self.viewport.fraction(self._position)
        for channel, lane in enumerate(self.lane_rects()):
            appearance = self._channel_appearance(channel)
            style = get_painter(appearance.style)
            self._paint_guides(painter, lane, appearance)
            buckets = style.buckets(lane.width(), style.resolve(appearance))
            self._renderers[channel].paint(
                painter,
                lane.adjusted(0, 4, 0, -4),
                self._lane_peaks(channel, buckets),
                appearance,
                progress,
                token=(self._token, channel, buckets),
            )
            if channel:
                painter.setPen(QColor(appearance.palette.grid))
                painter.drawLine(QPointF(0, lane.top() - LANE_GAP / 2), QPointF(lane.right(), lane.top() - LANE_GAP / 2))

    def _paint_guides(self, painter: QPainter, lane: QRectF, appearance: Appearance) -> None:
        grid = QColor(appearance.palette.grid)
        if appearance.show_grid:
            faint = QColor(grid)
            faint.setAlpha(140)
            painter.setPen(QPen(faint, 1))
            for t in self.major_tick_times():
                x = round(self.time_to_x(t)) + 0.5
                painter.drawLine(QPointF(x, lane.top()), QPointF(x, lane.bottom()))
            for fraction in (0.25, 0.75):
                y = round(lane.top() + lane.height() * fraction) + 0.5
                painter.drawLine(QPointF(lane.left(), y), QPointF(lane.right(), y))
        if appearance.show_midline:
            painter.setPen(QPen(grid.lighter(130), 1, Qt.PenStyle.DashLine))
            y = round(lane.center().y()) + 0.5
            painter.drawLine(QPointF(lane.left(), y), QPointF(lane.right(), y))

    def paint_playhead_marks(self, painter: QPainter, x: float) -> None:
        for channel, lane in enumerate(self.lane_rects()):
            appearance = self._channel_appearance(channel)
            radius = appearance.playhead_radius
            if radius <= 0:
                continue
            painter.setBrush(QColor(appearance.palette.played))
            painter.setPen(QPen(QColor(appearance.palette.background), 2))
            painter.drawEllipse(QPointF(x, lane.center().y()), radius, radius)
