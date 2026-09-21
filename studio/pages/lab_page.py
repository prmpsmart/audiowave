"""Style Lab: every registered waveform style and analysis view, live, side by side."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from audiowave.widgets import (
    SpectrogramView,
    VectorscopeView,
    get_painter,
    painter_names,
)
from studio.demo import demo_clip
from studio.models import AppearanceModel
from studio.session import Session
from studio.theme import get_theme
from studio.widgets import set_property
from studio.widgets.style_picker import paint_preview


@dataclass(frozen=True)
class StyleInfo:
    description: str
    api: str
    cost: str


STYLE_INFO: dict[str, StyleInfo] = {
    "bars": StyleInfo(
        "The original look: fixed-width bars around a midline. Width, spacing, radius and gravity all apply.",
        "drawRects",
        "low",
    ),
    "capsule": StyleInfo(
        "Bars with fully round ends. Friendlier on short clips and voice notes.",
        "addRoundedRect · r = w/2",
        "low",
    ),
    "hair": StyleInfo(
        "One-pixel needles for dense, long recordings. Pairs well with zoom.",
        "drawRects · 1 px",
        "low",
    ),
    "env": StyleInfo(
        "A filled silhouette of the min/max data. Clean at any zoom and cheap to repaint.",
        "QPainterPath · fillPath",
        "low",
    ),
    "line": StyleInfo(
        "Two spline curves through peaks and troughs over a faint fill. Calm and editorial.",
        "QPainterPath.quadTo",
        "low",
    ),
    "stairs": StyleInfo(
        "A stepped silhouette that keeps every bucket visible. Honest about resolution.",
        "QPainterPath.lineTo",
        "low",
    ),
    "dots": StyleInfo(
        "Stacked dots per column like an LED meter, fading towards the tips.",
        "addEllipse · alpha fade",
        "med",
    ),
    "rms": StyleInfo(
        "A bright RMS core inside a dim peak halo. Shows perceived loudness, not only spikes.",
        "2 passes · alpha 0.32",
        "low",
    ),
    "ground": StyleInfo(
        "Bars stand on a baseline with a fading reflection. Made for “now playing” cards.",
        "QLinearGradient",
        "low",
    ),
    "radial": StyleInfo(
        "Bars around a ring that fills clockwise as it plays. Fits covers and round buttons.",
        "arcTo clip · drawLines",
        "low",
    ),
}
_ORDER = [
    "bars",
    "capsule",
    "hair",
    "env",
    "line",
    "stairs",
    "dots",
    "rms",
    "ground",
    "radial",
]


class _Canvas(QWidget):
    """Draws one style with the current appearance and the demo audio."""

    def __init__(self, style: str, model: AppearanceModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._style, self._model = style, model
        self.setMinimumHeight(118)
        model.changed.connect(self.update)

    def paintEvent(self, _: QPaintEvent) -> None:
        t = get_theme()
        a = self._model.appearance(0).with_(style=self._style)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor(a.palette.background))
        rect = QRectF(8, 6, self.width() - 16, self.height() - 12)
        if self._style not in ("radial", "ground"):
            p.setPen(QPen(QColor(t.line2), 1, Qt.PenStyle.DashLine))
            p.drawLine(
                int(rect.left()),
                int(rect.center().y()),
                int(rect.right()),
                int(rect.center().y()),
            )
        paint_preview(p, rect, a)
        if self._style != "radial":
            p.setPen(QPen(QColor(a.palette.playhead), 1.2))
            p.drawLine(
                int(rect.center().x()),
                int(rect.top()),
                int(rect.center().x()),
                int(rect.bottom()),
            )
        p.end()


class _Tile(QFrame):
    def __init__(
        self,
        title: str,
        tag: str,
        tag_kind: str,
        description: str,
        api: str,
        cost: str,
        body: QWidget,
    ) -> None:
        super().__init__()
        self.setObjectName("tile")
        col = QVBoxLayout(self)
        col.setContentsMargins(10, 10, 10, 10)
        col.setSpacing(7)
        frame = QFrame()
        frame.setObjectName("well")
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(0, 0, 0, 0)
        inner.addWidget(body)
        col.addWidget(frame, 1)
        head = QHBoxLayout()
        name = QLabel(title)
        name.setObjectName("h2")
        badge = QLabel(tag.upper())
        badge.setProperty("tag", True)
        badge.setStyleSheet(
            f"background: {get_theme().teal if tag_kind == 'numpy' else get_theme().accent};"
        )
        head.addWidget(name)
        head.addStretch()
        head.addWidget(badge)
        col.addLayout(head)
        text = QLabel(description)
        text.setObjectName("muted")
        text.setWordWrap(True)
        col.addWidget(text)
        foot = QHBoxLayout()
        code = QLabel(api)
        code.setObjectName("subtime")
        price = QLabel(f"cost · {cost}")
        price.setObjectName("subtime")
        foot.addWidget(code)
        foot.addStretch()
        foot.addWidget(price)
        col.addLayout(foot)
        self.style_name: str | None = None


class LabPage(QWidget):
    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model = session.appearance
        self._tiles: dict[str, _Tile] = {}

        col = QVBoxLayout(self)
        col.setContentsMargins(22, 16, 22, 18)
        col.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel(f'Style <i style="color:{get_theme().accent}">Lab</i>')
        title.setObjectName("h1")
        title.setTextFormat(Qt.TextFormat.RichText)
        blurb = QLabel(
            "Every look is one paint routine over the same min/max data, so any of them can be chosen per channel "
            "and mixed. Ten are plain QPainter; two need numpy for the FFT or the stereo maths. Click a tile to use it."
        )
        blurb.setObjectName("muted")
        blurb.setWordWrap(True)
        head.addWidget(title)
        head.addSpacing(30)
        head.addWidget(blurb, 1)
        col.addLayout(head)

        grid = QGridLayout()
        grid.setSpacing(12)
        names = [n for n in _ORDER if n in painter_names()] + [
            n for n in painter_names() if n not in _ORDER
        ]
        for i, name in enumerate(names):
            info = STYLE_INFO.get(name, StyleInfo(get_painter(name).label, "custom painter", "?"))
            tile = _Tile(
                get_painter(name).label,
                "QPainter",
                "qt",
                info.description,
                info.api,
                info.cost,
                _Canvas(name, self._model),
            )
            tile.style_name = name
            tile.mousePressEvent = lambda e, n=name: self._choose(e, n)  # type: ignore[method-assign]
            tile.setCursor(Qt.CursorShape.PointingHandCursor)
            self._tiles[name] = tile
            grid.addWidget(tile, i // 4, i % 4)

        demo = demo_clip()
        spectro = SpectrogramView()
        spectro.set_ruler_visible(False)
        spectro.set_clip(demo)
        spectro.setMinimumHeight(118)
        scope = VectorscopeView()
        scope.set_clip(demo)
        loudest = int(abs(demo.channel(0)).argmax())
        scope.set_position(loudest / demo.sample_rate + 0.02)
        scope.setMinimumHeight(118)
        self._views = (spectro, scope)
        for j, (title_, tag, desc, api, cost, body) in enumerate(
            [
                (
                    "Spectrogram",
                    "numpy · FFT",
                    "Frequency over time, heat-mapped. One FFT per window, painted once into a QImage and cached.",
                    "np.fft.rfft → QImage",
                    "high",
                    spectro,
                ),
                (
                    "Vectorscope",
                    "numpy",
                    "Left against right as an XY plot. A thin line is mono; a wide cloud is a wide stereo image.",
                    "drawPoints · alpha trail",
                    "med",
                    scope,
                ),
            ]
        ):
            n = len(names) + j
            grid.addWidget(_Tile(title_, tag, "numpy", desc, api, cost, body), n // 4, n % 4)
        col.addLayout(grid, 1)

        self._model.changed.connect(self._sync)
        self._sync()

    def _choose(self, _: QMouseEvent, name: str) -> None:
        self._model.update(style=name)

    def _sync(self) -> None:
        current = self._model.editing.style
        for name, tile in self._tiles.items():
            set_property(tile, "selected", name == current)
        palette = self._model.appearance(0).palette
        for view in self._views:
            view.set_theme(palette)

    def refresh_theme(self) -> None:
        self._sync()
