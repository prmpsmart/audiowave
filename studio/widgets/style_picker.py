"""StylePicker: a grid of live thumbnails, one per waveform style, drawn by the library's own painters."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QAbstractButton, QGridLayout, QWidget

from audiowave import Appearance, Palette, Peaks
from audiowave.widgets import get_painter
from audiowave.widgets.lane import LaneRenderer
from studio.demo import demo_clip, demo_peaks
from studio.theme import get_theme

_peaks_cache: dict[int, Peaks] = {}


def preview_peaks(buckets: int, whole: bool = False) -> Peaks:
    """The demo clip's envelope (a fixed slice, or all of it), cached per request."""
    key = -buckets if whole else buckets
    if key not in _peaks_cache:
        span = (0.0, None) if whole else (1.0, 3.6)
        _peaks_cache[key] = demo_peaks(buckets, demo_clip(), *span)
    return _peaks_cache[key]


def paint_preview(
    painter: QPainter, rect: QRectF, appearance: Appearance, progress: float = 0.5
) -> None:
    """Draw ``appearance`` into ``rect`` using the demo audio (no caching: thumbnails are tiny)."""
    style = get_painter(appearance.style)
    buckets = style.buckets(rect.width(), style.resolve(appearance))
    LaneRenderer().paint(
        painter, rect, preview_peaks(buckets, style.full_span), appearance, progress
    )


class _Thumb(QAbstractButton):
    def __init__(self, style: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.style_name, self._label = style, label
        self._palette = Palette()
        self.setCheckable(True)
        self.setFixedHeight(62)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(label)

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def paintEvent(self, _: QPaintEvent) -> None:
        t = get_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(
            QPen(QColor(t.accent if self.isChecked() else t.line), 1.5 if self.isChecked() else 1)
        )
        p.setBrush(QColor(t.bg))
        p.drawRoundedRect(QRectF(0.75, 0.75, self.width() - 1.5, self.height() - 1.5), 8, 8)
        appearance = Appearance(
            style=self.style_name,
            bar_width=2.4,
            bar_spacing=1.6,
            radius=1,
            show_midline=False,
            palette=self._palette,
        )
        paint_preview(p, QRectF(6, 5, self.width() - 12, self.height() - 26), appearance)
        p.setPen(QColor(t.text if self.isChecked() else t.muted))
        font = p.font()
        font.setPixelSize(10)
        p.setFont(font)
        p.drawText(
            QRectF(0, self.height() - 19, self.width(), 16),
            int(Qt.AlignmentFlag.AlignCenter),
            self._label,
        )
        p.end()


class StylePicker(QWidget):
    """Choose a waveform style. Emits ``styleChosen(name)``."""

    styleChosen = Signal(str)

    def __init__(self, styles: list[str], columns: int = 4, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(7)
        self._thumbs: dict[str, _Thumb] = {}
        for i, name in enumerate(styles):
            thumb = _Thumb(name, get_painter(name).label)
            thumb.clicked.connect(lambda _=False, n=name: self._choose(n))
            self._thumbs[name] = thumb
            grid.addWidget(thumb, i // columns, i % columns)

    def set_current(self, style: str) -> None:
        for name, thumb in self._thumbs.items():
            thumb.setChecked(name == style)

    def set_palette(self, palette: Palette) -> None:
        for thumb in self._thumbs.values():
            thumb.set_palette(palette)

    def _choose(self, name: str) -> None:
        self.set_current(name)
        self.styleChosen.emit(name)
