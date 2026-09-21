"""Session: the shared state and services the pages work with."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Signal

from audiowave import AudioClip, Loop, Marker
from audiowave.audio import AudioDecoder, AudioDevice, AudioPlayer, AudioRecorder, is_supported
from audiowave.core import Loudness, WavError, edit
from audiowave.widgets import Viewport

from .editing import EditError, apply_action, measure
from .models import AppearanceModel, PresetStore, RecentFiles, Take, TakesModel
from .tasks import BackgroundTasks

_LOUDNESS_CACHE = 12


class Session(QObject):
    """Owns the player, recorder and models, and the state that spans pages (loop, markers, viewport).

    Pages receive a Session instead of reaching into each other, so none of them depend on another.
    """

    clipChanged = Signal(object)  # AudioClip | None
    loopChanged = Signal(object)  # Loop | None (the selection)
    loopEnabledChanged = Signal(bool)
    markersChanged = Signal(object)  # list[Marker]
    silencesChanged = Signal(object)  # list[Loop]
    loudnessChanged = Signal(object)  # Loudness | None, for the current clip
    busyChanged = Signal(bool)  # a background edit is running
    decodeProgress = Signal(float)
    message = Signal(str, bool)  # text, is_error

    def __init__(
        self,
        player: AudioPlayer,
        recorder: AudioRecorder,
        appearance: AppearanceModel,
        takes: TakesModel,
        presets: PresetStore,
        recent: RecentFiles | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.player, self.recorder = player, recorder
        self.appearance, self.takes, self.presets, self.recent = appearance, takes, presets, recent
        self.viewport = Viewport(self)
        self.tasks = BackgroundTasks(self)
        self.input_device: AudioDevice | None = None  # None = system default

        self._loop: Loop | None = None
        self._loop_enabled = False
        self._markers: list[Marker] = []
        self._silences: list[Loop] = []
        self._loudness: Loudness | None = None
        self._loudness_cache: dict[int, tuple[AudioClip, Loudness]] = {}
        self._busy = False
        self._decoders: set[AudioDecoder] = set()

        self.takes.currentChanged.connect(self._on_take)
        self.takes.clipChanged.connect(self._on_clip_edited)
        self.player.errorOccurred.connect(lambda text: self.message.emit(text, True))
        self.recorder.errorOccurred.connect(lambda text: self.message.emit(text, True))

    # -- devices --------------------------------------------------------------------------------

    def set_input_device(self, device: AudioDevice | None) -> None:
        self.input_device = device

    def set_output_device(self, device: AudioDevice | None) -> None:
        self.player.set_output_device(device.native if device else None)

    # -- opening and saving ---------------------------------------------------------------------

    @property
    def clip(self) -> AudioClip | None:
        return self.takes.current.clip if self.takes.current else None

    def open_file(self, path: str | Path, select: bool = True) -> Take | None:
        """Open an audio file as a take.

        WAV loads immediately and the take is returned. Other formats (mp3, flac, ogg, m4a...) decode in
        the background, so this returns ``None`` and the take appears in ``takes`` when decoding finishes.
        """
        path = Path(path)
        if not path.is_file():
            self.message.emit(f"File not found: {path.name}", True)
            return None
        if not is_supported(path):
            self.message.emit(f"{path.suffix or path.name} is not a supported audio format", True)
            return None
        if self.recent is not None:
            self.recent.add(path)
        if path.suffix.lower() == ".wav":
            try:
                return self.takes.add(
                    AudioClip.from_wav(path), name=path.stem, path=path, select=select
                )
            except (OSError, WavError):
                pass  # an unusual WAV (e.g. ADPCM): let the decoder have a go
        self._decode_async(path, select)
        return None

    def _decode_async(self, path: Path, select: bool) -> None:
        decoder = AudioDecoder(self)
        self._decoders.add(decoder)
        self.message.emit(f"Decoding {path.name}…", False)

        def finish() -> None:
            self._decoders.discard(decoder)
            decoder.deleteLater()

        def done(clip: AudioClip) -> None:
            finish()
            self.takes.add(clip, name=path.stem, path=path, select=select)
            self.message.emit(f"Opened {path.name}", False)

        def failed(text: str) -> None:
            finish()
            self.message.emit(f"Could not open {path.name}: {text}", True)

        decoder.progress.connect(self.decodeProgress)
        decoder.decoded.connect(done)
        decoder.failed.connect(failed)
        decoder.decode(path)

    def save_take(self, take: Take, path: str | Path) -> bool:
        try:
            take.clip.to_wav(path)
        except OSError as error:
            self.message.emit(f"Could not save: {error}", True)
            return False
        take.path, take.dirty = Path(path), False
        self.message.emit(f"Saved {Path(path).name}", False)
        return True

    # -- current take ---------------------------------------------------------------------------

    def _on_take(self, take: Take | None) -> None:
        self._reload(take.clip if take else None, keep_position=False)

    def _on_clip_edited(self, take: Take, label: str) -> None:
        if take is self.takes.current:
            self._reload(take.clip, keep_position=True)
        self.message.emit(label, False)

    def _reload(self, clip: AudioClip | None, keep_position: bool) -> None:
        was_playing = self.player.state.value == "playing"
        position = self.player.position if keep_position else 0.0
        self._loop, self._markers, self._silences, self._loudness = None, [], [], None
        self.player.load(clip)
        self.player.set_loop(None)
        self.viewport.set_duration(clip.duration if clip else 0.0)
        if clip is not None and keep_position and position > 0:
            self.player.seek(min(position, clip.duration))
            if was_playing:
                self.player.play()
        self.clipChanged.emit(clip)
        self.loopChanged.emit(None)
        self.markersChanged.emit([])
        self.silencesChanged.emit([])
        self.loudnessChanged.emit(None)
        if clip is not None:
            self.loudness_of(clip, lambda result, c=clip: self._on_loudness(c, result))

    # -- loudness -------------------------------------------------------------------------------

    @property
    def loudness(self) -> Loudness | None:
        return self._loudness

    def _on_loudness(self, clip: AudioClip, result: Loudness) -> None:
        if clip is self.clip:
            self._loudness = result
            self.loudnessChanged.emit(result)

    def loudness_of(self, clip: AudioClip, callback) -> None:
        """Measure ``clip`` in the background (cached) and call ``callback(Loudness)`` on the UI thread."""
        cached = self._loudness_cache.get(id(clip))
        if cached is not None and cached[0] is clip:
            callback(cached[1])
            return

        def store(result: Loudness) -> None:
            self._loudness_cache[id(clip)] = (
                clip,
                result,
            )  # holding ``clip`` keeps its id from being reused
            while len(self._loudness_cache) > _LOUDNESS_CACHE:
                self._loudness_cache.pop(next(iter(self._loudness_cache)))
            callback(result)

        self.tasks.submit(f"loudness-{id(clip)}", lambda: measure(clip), store)

    # -- loop / selection -----------------------------------------------------------------------

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

    # -- silence --------------------------------------------------------------------------------

    @property
    def silences(self) -> list[Loop]:
        return list(self._silences)

    def find_silences(self, threshold_db: float = -50.0, min_duration: float = 0.3) -> None:
        clip = self.clip
        if clip is None:
            return

        def found(ranges: list[tuple[float, float]]) -> None:
            if clip is not self.clip:
                return  # the clip changed while analysing
            self._silences = [Loop(a, b) for a, b in ranges]
            self.silencesChanged.emit(self.silences)
            n = len(ranges)
            self.message.emit(
                f"Found {n} silence{'s' if n != 1 else ''}" if n else "No silences found", False
            )

        self.tasks.submit(
            "silences", lambda: edit.silent_ranges(clip, threshold_db, min_duration), found
        )

    def clear_silences(self) -> None:
        self._silences = []
        self.silencesChanged.emit([])

    # -- editing --------------------------------------------------------------------------------

    @property
    def busy(self) -> bool:
        return self._busy

    def run_edit(self, action: str, value: float | None = None) -> None:
        """Apply an editing action to the current take, in the background, with undo."""
        take = self.takes.current
        if take is None:
            return
        if self._busy:
            self.message.emit("Still working on the previous edit…", True)
            return
        clip, selection, silences = take.clip, self._loop, list(self._silences)
        self._set_busy(True)

        def work():
            try:
                return apply_action(action, clip, selection, value, silences)
            except EditError as error:
                return error  # returned, not raised, so the message reaches the UI untouched

        def done(result) -> None:
            self._set_busy(False)
            if isinstance(result, EditError):
                self.message.emit(str(result), True)
            elif take in list(self.takes):
                new_clip, label = result
                self.takes.apply_edit(take, new_clip, label)

        def failed(text: str) -> None:
            self._set_busy(False)
            self.message.emit(f"Edit failed: {text}", True)

        self.tasks.submit("edit", work, done, failed)

    def undo(self) -> None:
        take = self.takes.current
        if take is not None and not self.takes.undo(take):
            self.message.emit("Nothing to undo", False)

    def redo(self) -> None:
        take = self.takes.current
        if take is not None and not self.takes.redo(take):
            self.message.emit("Nothing to redo", False)

    def _set_busy(self, busy: bool) -> None:
        if busy != self._busy:
            self._busy = busy
            self.busyChanged.emit(busy)

    # -- lifecycle ------------------------------------------------------------------------------

    def shutdown(self) -> None:
        for decoder in list(self._decoders):
            decoder.cancel()
        self.tasks.shutdown()
