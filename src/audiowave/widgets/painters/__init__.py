"""Waveform styles. Importing this package registers every built-in style."""

# Imported for their @register side effect.
from . import bars, marks, outlines
from .base import PaintJob, WavePainter
from .registry import DEFAULT_STYLE, get_painter, painter_names, painters, register

__all__ = [
    "DEFAULT_STYLE",
    "PaintJob",
    "WavePainter",
    "get_painter",
    "painter_names",
    "painters",
    "register",
]
