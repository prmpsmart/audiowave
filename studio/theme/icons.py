"""Stroke icons drawn from SVG paths, recoloured on demand so they follow the theme."""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# name -> (path data, filled?)
_ICONS: dict[str, tuple[str, bool]] = {
    "play": ("M7 4.5v15l12-7.5z", True),
    "pause": ("M7 5h3.5v14H7zM13.5 5H17v14h-3.5z", True),
    "stop": ("M6 6h12v12H6z", True),
    "rec": ("M12 5.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13z", True),
    "loop": (
        "M17 2l3 3-3 3M20 5H8a4 4 0 0 0-4 4v1M7 22l-3-3 3-3M4 19h12a4 4 0 0 0 4-4v-1",
        False,
    ),
    "back": ("M6 5v14M19 5L9 12l10 7z", False),
    "vol": ("M4 9v6h4l5 4V5L8 9zM16.5 8.5a5 5 0 0 1 0 7", False),
    "save": ("M12 4v11M7 11l5 5 5-5M5 20h14", False),
    "image": ("M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4", False),
    "folder": ("M3 7h6l2 2h10v10H3z", False),
    "mic": (
        "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
        False,
    ),
    "chain": (
        "M10 14a4 4 0 0 0 5.6 0l3-3a4 4 0 0 0-5.6-5.6l-1 1M14 10a4 4 0 0 0-5.6 0l-3 3a4 4 0 0 0 5.6 5.6l1-1",
        False,
    ),
    "net": (
        "M3 9a14 14 0 0 1 18 0M6 12.5a9 9 0 0 1 12 0M9 16a4 4 0 0 1 6 0M12 19.5h.01",
        False,
    ),
    "flag": ("M6 21V4M6 5h11l-2 4 2 4H6", False),
    "lab": ("M9 3h6M10 3v6l-5 9a2 2 0 0 0 2 3h10a2 2 0 0 0 2-3l-5-9V3M8 15h8", False),
    "sun": (
        "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5L19 19M5 19l1.5-1.5M17.5 6.5L19 5",
        False,
    ),
    "moon": ("M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z", False),
    "plus": ("M12 5v14M5 12h14", False),
    "dots": ("M5 12h.01M12 12h.01M19 12h.01", False),
    "trash": ("M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13", False),
    "chev": ("M6 9l6 6 6-6", False),
    "check": ("M5 12l5 5 9-10", False),
    "wave": ("M3 12h2M7 8v8M11 4v16M15 7v10M19 10v4", False),
}


def icon_names() -> list[str]:
    return list(_ICONS)


@lru_cache(maxsize=512)
def _pixmap(name: str, color: str, size: int, dpr: float) -> QPixmap:
    path, filled = _ICONS[name]
    fill, stroke = (color, "none") if filled else ("none", color)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
        f'<path d="{path}"/></svg>'
    )
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    pixmap = QPixmap(int(size * dpr), int(size * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def icon(name: str, color: str | QColor = "#ece6d6", size: int = 18, dpr: float = 2.0) -> QIcon:
    """A ``QIcon`` of the named glyph in ``color`` (hex string or QColor)."""
    hex_color = QColor(color).name()
    return QIcon(_pixmap(name, hex_color, size, dpr))


def pixmap(name: str, color: str | QColor, size: int = 18, dpr: float = 2.0) -> QPixmap:
    return _pixmap(name, QColor(color).name(), size, dpr)
