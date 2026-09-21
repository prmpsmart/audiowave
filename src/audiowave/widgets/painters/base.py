"""The contract every waveform style implements, plus the geometry helpers they share."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

import numpy as np
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath

from audiowave.appearance import Appearance, Gravity
from audiowave.core.peaks import Peaks


@dataclass(frozen=True)
class PaintJob:
    """Everything a painter needs for one channel lane."""

    rect: QRectF
    peaks: Peaks
    appearance: Appearance


class WavePainter(ABC):
    """Draws one channel's envelope in a single colour.

    A painter never decides played-vs-unplayed colouring. It draws the whole shape once per colour
    and the lane renderer clips each drawing to the right region. That keeps every style free of
    playhead logic, and lets a style choose its own notion of "played" via :meth:`played_region`.
    """

    name: ClassVar[str]
    label: ClassVar[str]
    #: Whether ``bar_width`` / ``bar_spacing`` / ``radius`` mean anything for this style.
    uses_bar_shape: ClassVar[bool] = False
    #: Whether the gravity setting changes the result.
    uses_gravity: ClassVar[bool] = True
    #: True for styles that need the whole clip's envelope even in a small preview (e.g. a ring).
    full_span: ClassVar[bool] = False

    def resolve(self, appearance: Appearance) -> Appearance:
        """Adjust the user's settings for this style (e.g. force a radius). Default: unchanged."""
        return appearance

    def buckets(self, width: float, appearance: Appearance) -> int:
        """How many envelope buckets fit in ``width`` pixels."""
        return max(int(width // (appearance.bar_width + appearance.bar_spacing)), 1)

    def played_region(self, rect: QRectF, progress: float) -> QRectF | QPainterPath:
        """The part of ``rect`` that counts as already played. Default: everything left of the playhead."""
        return QRectF(
            rect.left(), rect.top(), rect.width() * min(max(progress, 0.0), 1.0), rect.height()
        )

    @abstractmethod
    def paint(self, painter: QPainter, job: PaintJob, color: QColor) -> None:
        """Draw the envelope. Must not change painter state it does not restore."""


# -- shared geometry ------------------------------------------------------------------------------


def half_height(job: PaintJob) -> float:
    return job.rect.height() / 2 * job.appearance.scale


def extents(job: PaintJob) -> tuple[np.ndarray, np.ndarray]:
    """Pixels each bucket extends above and below the midline, honouring gravity and idle height."""
    a, p = job.appearance, job.peaks
    half = half_height(job)
    floor = a.idle_height / 2
    zero = np.zeros(len(p))
    if a.gravity is Gravity.AVERAGE:
        up = down = np.maximum(p.amplitude * half, floor)
    elif a.gravity is Gravity.MIN_MAX:
        up = np.maximum(np.maximum(p.maximum, 0) * half, floor)
        down = np.maximum(np.maximum(-p.minimum, 0) * half, floor)
    elif a.gravity is Gravity.MAX:
        up, down = np.maximum(np.maximum(p.maximum, 0) * half, a.idle_height), zero
    else:
        up, down = zero, np.maximum(np.maximum(-p.minimum, 0) * half, a.idle_height)
    return up.astype(np.float64), down.astype(np.float64)


def column_x(job: PaintJob) -> np.ndarray:
    """Left edge of each bar, with the whole run centred in the lane."""
    a = job.appearance
    step = a.bar_width + a.bar_spacing
    n = len(job.peaks)
    used = n * step - a.bar_spacing
    return job.rect.left() + (job.rect.width() - used) / 2 + np.arange(n) * step
