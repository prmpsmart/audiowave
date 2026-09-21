"""The visible time window of a timeline. Shared by every widget that should scroll and zoom together."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class Viewport(QObject):
    """A ``[start, end]`` window (seconds) inside ``[0, duration]``.

    Widgets sharing one viewport (waveform, spectrogram, overview) stay in sync without knowing
    about each other. All mutators clamp, so callers never need to validate.
    """

    changed = Signal()

    #: Smallest visible span in seconds.
    MIN_SPAN = 0.02

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._duration = 0.0
        self._start = 0.0
        self._end = 0.0

    # -- state ----------------------------------------------------------------------------------

    @property
    def duration(self) -> float:
        return self._duration

    @property
    def start(self) -> float:
        return self._start

    @property
    def end(self) -> float:
        return self._end

    @property
    def span(self) -> float:
        return self._end - self._start

    @property
    def is_full(self) -> bool:
        return self._duration > 0 and self.span >= self._duration - 1e-9

    @property
    def zoom_level(self) -> float:
        """How many times the full duration fits in the window (1.0 = fully zoomed out)."""
        return self._duration / self.span if self.span > 0 else 1.0

    def fraction(self, t: float) -> float:
        """Position of ``t`` inside the window, 0 at the left edge and 1 at the right."""
        return (t - self._start) / self.span if self.span > 0 else 0.0

    # -- mutators -------------------------------------------------------------------------------

    def set_duration(self, duration: float) -> None:
        """Set the total length and show all of it."""
        self._duration = max(float(duration), 0.0)
        self._start, self._end = 0.0, self._duration
        self.changed.emit()

    def set_range(self, start: float, end: float) -> None:
        if self._duration <= 0:
            return
        span = min(max(end - start, min(self.MIN_SPAN, self._duration)), self._duration)
        start = min(max(start, 0.0), self._duration - span)
        self._apply(start, start + span)

    def fit(self) -> None:
        self.set_range(0.0, self._duration)

    def zoom(self, factor: float, anchor: float | None = None) -> None:
        """Zoom in by ``factor`` (>1 in, <1 out), keeping ``anchor`` (seconds) fixed on screen."""
        if factor <= 0 or self.span <= 0:
            return
        anchor = (self._start + self._end) / 2 if anchor is None else anchor
        frac = self.fraction(anchor)
        new_span = min(max(self.span / factor, self.MIN_SPAN), self._duration)
        start = anchor - frac * new_span
        self.set_range(start, start + new_span)

    def pan(self, delta: float) -> None:
        self.set_range(self._start + delta, self._end + delta)

    def ensure_visible(self, t: float, lead: float = 0.1) -> None:
        """Scroll (never zoom) so that ``t`` is on screen, leaving ``lead`` of the span behind it."""
        if self.is_full:
            return
        if not (self._start <= t <= self._end - 0.02 * self.span):
            self.pan(t - self._start - lead * self.span)

    def _apply(self, start: float, end: float) -> None:
        if abs(start - self._start) > 1e-12 or abs(end - self._end) > 1e-12:
            self._start, self._end = start, end
            self.changed.emit()
