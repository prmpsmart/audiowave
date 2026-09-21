"""Time-axis maths (pure functions) and the ruler painter."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter

from audiowave.appearance import Palette

_STEPS = (
    0.001, 0.002, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
    1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600,
)  # fmt: skip
_MINOR_DIVISIONS = {15: 3, 30: 3, 120: 4, 300: 5, 900: 3, 1800: 3}


def nice_step(span: float, width: float, min_label_px: float = 80.0) -> float:
    """Smallest 'round' tick spacing (seconds) that keeps labels at least ``min_label_px`` apart."""
    if span <= 0 or width <= 0:
        return 1.0
    wanted = span * min_label_px / width
    for step in _STEPS:
        if step >= wanted:
            return step
    return _STEPS[-1]


def ticks(start: float, end: float, step: float) -> list[tuple[float, bool]]:
    """``(time, is_major)`` for every tick in ``[start, end]``; majors fall on multiples of ``step``."""
    divisions = _MINOR_DIVISIONS.get(int(step), 5) if step >= 1 else 5
    minor = step / divisions
    first = math.floor(start / minor)
    last = math.ceil(end / minor)
    out = []
    for i in range(first, last + 1):
        t = i * minor
        if start - 1e-9 <= t <= end + 1e-9:
            out.append((t, i % divisions == 0))
    return out


def format_time(t: float, step: float = 1.0) -> str:
    """``m:ss`` with as many decimals as ``step`` needs (``h:mm:ss`` past an hour)."""
    t = max(t, 0.0)
    decimals = 0 if step >= 1 else 1 if step >= 0.1 else 2 if step >= 0.01 else 3
    total = round(t, decimals)
    hours, rem = divmod(int(total), 3600)
    minutes, seconds = divmod(rem, 60)
    frac = f".{round((total - int(total)) * 10**decimals):0{decimals}d}" if decimals else ""
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}{frac}"
    return f"{minutes}:{seconds:02d}{frac}"


def paint_ruler(
    painter: QPainter,
    rect: QRectF,
    start: float,
    end: float,
    palette: Palette,
    font: QFont,
    min_label_px: float = 80.0,
) -> float:
    """Draw ticks and labels for ``[start, end]`` across ``rect``. Returns the major tick step used."""
    span = end - start
    step = nice_step(span, rect.width(), min_label_px)
    if span <= 0:
        return step

    painter.save()
    painter.setFont(font)
    painter.setClipRect(rect)
    text, line = QColor(palette.text), QColor(palette.grid).lighter(160)
    painter.setPen(QColor(palette.grid))
    painter.drawLine(
        QPointF(rect.left(), rect.bottom() - 0.5),
        QPointF(rect.right(), rect.bottom() - 0.5),
    )

    for t, major in ticks(start, end, step):
        x = rect.left() + (t - start) / span * rect.width()
        height = 10 if major else 5
        painter.setPen(line if major else QColor(palette.grid))
        painter.drawLine(QPointF(x + 0.5, rect.bottom() - height), QPointF(x + 0.5, rect.bottom()))
        if major:
            painter.setPen(text)
            painter.drawText(
                QRectF(x + 4, rect.top(), 90, rect.height() - 8),
                int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                format_time(t, step),
            )
    painter.restore()
    return step
