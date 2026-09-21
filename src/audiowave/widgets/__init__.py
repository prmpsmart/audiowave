"""Qt widgets built on the core: waveform, timeline views and their building blocks."""

from .annotations import Loop, Marker
from .painters import WavePainter, get_painter, painter_names, painters, register
from .viewport import Viewport
from .waveform_view import WaveformView

__all__ = [
    "Loop",
    "Marker",
    "Viewport",
    "WavePainter",
    "WaveformView",
    "get_painter",
    "painter_names",
    "painters",
    "register",
]
