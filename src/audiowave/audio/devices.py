"""Audio device discovery."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtMultimedia import QAudioDevice, QMediaDevices


@dataclass(frozen=True)
class AudioDevice:
    """A named audio endpoint. ``native`` is the Qt handle to pass to the player or recorder."""

    id: bytes
    name: str
    is_default: bool
    native: QAudioDevice = field(compare=False, repr=False)


def _wrap(devices: list[QAudioDevice], default: QAudioDevice) -> list[AudioDevice]:
    default_id = bytes(default.id()) if not default.isNull() else b""
    return [AudioDevice(bytes(d.id()), d.description(), bytes(d.id()) == default_id, d) for d in devices]


def input_devices() -> list[AudioDevice]:
    return _wrap(QMediaDevices.audioInputs(), QMediaDevices.defaultAudioInput())


def output_devices() -> list[AudioDevice]:
    return _wrap(QMediaDevices.audioOutputs(), QMediaDevices.defaultAudioOutput())


def default_input() -> AudioDevice | None:
    return next((d for d in input_devices() if d.is_default), None)


def default_output() -> AudioDevice | None:
    return next((d for d in output_devices() if d.is_default), None)


def find_device(devices: list[AudioDevice], device_id: bytes) -> AudioDevice | None:
    return next((d for d in devices if d.id == device_id), None)
