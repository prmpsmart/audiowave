"""audiowave: waveform widgets, analysis and playback for PySide6.

Layers, from independent to dependent:

* ``audiowave.core``    decoding, peak envelopes, analysis. Only needs numpy.
* ``audiowave.appearance``  immutable style settings (also Qt-free).
* ``audiowave.audio``   playback and recording on QtMultimedia.
* ``audiowave.widgets`` the waveform and companion views.
* ``audiowave.binding`` connects a player to views.

Importing ``audiowave`` itself pulls in no Qt.
"""

from .appearance import Appearance, Gravity, Palette
from .core import (
    AudioClip,
    AudioFormat,
    ClipPeaks,
    LivePeaks,
    Loop,
    Marker,
    Peaks,
    SampleFormat,
)

__version__ = "0.2.0"

__all__ = [
    "Appearance",
    "AudioClip",
    "AudioFormat",
    "ClipPeaks",
    "Gravity",
    "LivePeaks",
    "Loop",
    "Marker",
    "Palette",
    "Peaks",
    "SampleFormat",
    "__version__",
]
