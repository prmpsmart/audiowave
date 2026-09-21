"""Qt-free core: decoding, envelopes and analysis. Depends only on numpy."""

from .analysis import (
    Spectrogram,
    correlation,
    detect_silence,
    from_db,
    peak_db,
    rms_db,
    spectrogram,
    stereo_xy,
    to_db,
)
from .clip import AudioClip
from .format import AudioFormat, SampleFormat, decode_pcm, encode_pcm
from .live import LivePeaks
from .peaks import ClipPeaks, PeakPyramid, Peaks
from .wavio import WavError, read_wav, wav_bytes, write_wav

__all__ = [
    "AudioClip",
    "AudioFormat",
    "ClipPeaks",
    "LivePeaks",
    "PeakPyramid",
    "Peaks",
    "SampleFormat",
    "Spectrogram",
    "WavError",
    "correlation",
    "decode_pcm",
    "detect_silence",
    "encode_pcm",
    "from_db",
    "peak_db",
    "read_wav",
    "rms_db",
    "spectrogram",
    "stereo_xy",
    "to_db",
    "wav_bytes",
    "write_wav",
]
