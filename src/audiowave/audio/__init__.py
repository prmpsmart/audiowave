"""Playback and capture on top of QtMultimedia."""

from .decode import (
    FILE_DIALOG_FILTER,
    SUPPORTED_EXTENSIONS,
    AudioDecoder,
    DecodeError,
    decode_file,
    is_supported,
    load_clip,
)
from .devices import (
    AudioDevice,
    default_input,
    default_output,
    find_device,
    input_devices,
    output_devices,
)
from .pcm_source import PcmSource
from .permissions import microphone_status, request_microphone
from .player import AudioPlayer, PlayerState
from .recorder import AudioRecorder, RecorderState

__all__ = [
    "FILE_DIALOG_FILTER",
    "SUPPORTED_EXTENSIONS",
    "AudioDecoder",
    "AudioDevice",
    "AudioPlayer",
    "AudioRecorder",
    "DecodeError",
    "PcmSource",
    "PlayerState",
    "RecorderState",
    "decode_file",
    "default_input",
    "default_output",
    "find_device",
    "input_devices",
    "is_supported",
    "load_clip",
    "microphone_status",
    "output_devices",
    "request_microphone",
]
