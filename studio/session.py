"""Session: the shared state and services the pages work with."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from audiowave import AudioClip, Loop, Marker
from audiowave.audio import AudioDevice, AudioPlayer, AudioRecorder
from audiowave.core import WavError
from audiowave.widgets import Viewport

from .models import AppearanceModel, PresetStore, Take, TakesModel


class Session(QObject):
    """Owns the player, recorder and models, and the state that spans pages (loop, markers, viewport).

    Pages receive a Session instead of reaching into each other, so none of them depend on another.
    """

    clipChanged = Signal(object)  # AudioClip | None
    loopChanged = Signal(object)  # Loop | None
    loopEnabledChanged = Signal(bool)
    markersChanged = Signal(object)  # list[Marker]
    message = Signal(str, bool)  # text, is_error

    def __init__(
        self,
        player: AudioPlayer,
        recorder: AudioRecorder,
        appearance: AppearanceModel,
        takes: TakesModel,
        presets: PresetStore,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.player, self.recorder = player, recorder
        self.appearance, self.takes, self.presets = appearance, takes, presets
        self.viewport = Viewport(self)
        self.input_device: AudioDevice | None = None  # None = system default

        self._loop: Loop | None = None
        self._loop_enabled = False
        self._markers: list[Marker] = []

        self.takes.currentChanged.connect(self._on_take)
        self.player.errorOccurred.connect(lambda text: self.message.emit(text, True))
        self.recorder.errorOccurred.connect(lambda text: self.message.emit(text, True))

    # -- devices --------------------------------------------------------------------------------

    def set_input_device(self, device: AudioDevice | None) -> None:
        self.input_device = device

    def set_output_device(self, device: AudioDevice | None) -> None:
        self.player.set_output_device(device.native if device else None)

    # -- clip / takes ---------------------------------------------------------------------------

    @property
    def clip(self) -> AudioClip | None:
        return self.takes.current.clip if self.takes.current else None

    def open_file(self, path: str | Path) -> Take | None:
        path = Path(path)
        try:
            clip = AudioClip.from_wav(path)
        except (OSError, WavError) as error:
            self.message.emit(f"Could not open {path.name}: {error}", True)
            return None
        return self.takes.add(clip, name=path.stem, path=path)

    def save_take(self, take: Take, path: str | Path) -> bool:
        try:
            take.clip.to_wav(path)
        except OSError as error:
            self.message.emit(f"Could not save: {error}", True)
            return False
        take.path = Path(path)
        self.message.emit(f"Saved {Path(path).name}", False)
        return True

    def _on_take(self, take: Take | None) -> None:
        self._loop, self._markers = None, []
        self.player.load(take.clip if take else None)
        self.player.set_loop(None)
        self.viewport.set_duration(take.clip.duration if take else 0.0)
        self.clipChanged.emit(take.clip if take else None)
        self.loopChanged.emit(None)
        self.markersChanged.emit([])

    # -- loop -----------------------------------------------------------------------------------

    @property
    def loop(self) -> Loop | None:
        return self._loop

    @property
    def loop_enabled(self) -> bool:
        return self._loop_enabled

    def set_loop_region(self, loop: Loop | None) -> None:
        self._loop = loop
        self.loopChanged.emit(loop)
        if loop is None:
            self.set_loop_enabled(False)
        elif not self._loop_enabled:
            self.set_loop_enabled(True)  # drawing a region means "loop this"
        else:
            self._apply_loop()

    def set_loop_enabled(self, enabled: bool) -> None:
        enabled = enabled and self._loop is not None
        if enabled != self._loop_enabled:
            self._loop_enabled = enabled
            self.loopEnabledChanged.emit(enabled)
        self._apply_loop()

    def _apply_loop(self) -> None:
        self.player.set_loop(self._loop if self._loop_enabled else None)

    # -- markers --------------------------------------------------------------------------------

    @property
    def markers(self) -> list[Marker]:
        return list(self._markers)

    def add_marker(self, time: float, label: str = "") -> None:
        self._markers.append(Marker(time, label or f"M{len(self._markers) + 1}"))
        self.markersChanged.emit(self.markers)

    def clear_markers(self) -> None:
        self._markers = []
        self.markersChanged.emit([])
