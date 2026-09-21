"""AudioPlayer: play an AudioClip with a device-accurate position, seek, loop, volume and speed."""

from __future__ import annotations

from enum import Enum

import numpy as np
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtMultimedia import QAudio, QAudioDevice, QAudioFormat, QAudioSink, QMediaDevices

from audiowave.core.clip import AudioClip
from audiowave.core.format import SampleFormat, encode_pcm
from audiowave.core.annotations import Loop

from .pcm_source import PcmSource

_TICK_MS = 16
MIN_SPEED, MAX_SPEED = 0.25, 4.0


class PlayerState(Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class AudioPlayer(QObject):
    """Plays one clip at a time.

    Position is derived from the audio device's own processed-time counter, not from a UI timer, so
    the playhead cannot drift from what is heard. Speed is varispeed (pitch follows), done by telling
    the device the stream runs at a scaled sample rate.
    """

    stateChanged = Signal(object)  # PlayerState
    positionChanged = Signal(float)  # seconds
    finished = Signal()
    errorOccurred = Signal(str)

    def __init__(self, parent: QObject | None = None, device: QAudioDevice | None = None) -> None:
        super().__init__(parent)
        self._device = device
        self._clip: AudioClip | None = None
        self._pcm = b""
        self._state = PlayerState.STOPPED
        self._volume = 1.0
        self._speed = 1.0
        self._loop: Loop | None = None
        self._gains: tuple[float, ...] | None = None  # per-channel gain; None = unity

        self._sink: QAudioSink | None = None
        self._source: PcmSource | None = None
        self._session_start = 0  # frame at which the current sink session began
        self._session_rate = 1  # sample rate the sink was told (source rate * speed)
        self._resting_frame = 0  # position while there is no session

        self._last_emitted = -1.0
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)

    # -- properties -----------------------------------------------------------------------------

    @property
    def clip(self) -> AudioClip | None:
        return self._clip

    @property
    def state(self) -> PlayerState:
        return self._state

    @property
    def duration(self) -> float:
        return self._clip.duration if self._clip else 0.0

    @property
    def volume(self) -> float:
        return self._volume

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def loop(self) -> Loop | None:
        return self._loop

    @property
    def position(self) -> float:
        if self._clip is None:
            return 0.0
        return self._current_frame() / self._clip.sample_rate

    # -- transport ------------------------------------------------------------------------------

    def load(self, clip: AudioClip | None) -> None:
        """Replace the current clip (stops playback)."""
        self._teardown()
        self._clip = clip
        self._gains = None
        self._pcm = self._encode()
        self._resting_frame = 0
        self._set_state(PlayerState.STOPPED)
        self._emit_position(force=True)

    def play(self) -> None:
        if self._clip is None or self._state is PlayerState.PLAYING:
            return
        if self._state is PlayerState.PAUSED and self._sink is not None:
            self._sink.resume()
        else:
            frame = self._resting_frame
            if frame >= self._clip.frames - 1:
                frame = self._loop_start_frame() if self._loop else 0
            if not self._start_session(frame):
                return
        self._set_state(PlayerState.PLAYING)
        self._timer.start()

    def pause(self) -> None:
        if self._state is not PlayerState.PLAYING or self._sink is None:
            return
        self._resting_frame = self._current_frame()
        self._sink.suspend()
        self._timer.stop()
        self._set_state(PlayerState.PAUSED)
        self._emit_position(force=True)

    def toggle(self) -> None:
        self.pause() if self._state is PlayerState.PLAYING else self.play()

    def stop(self) -> None:
        self._teardown()
        self._resting_frame = 0
        self._set_state(PlayerState.STOPPED)
        self._emit_position(force=True)

    def seek(self, seconds: float) -> None:
        if self._clip is None:
            return
        frame = self._clip.time_to_frame(seconds)
        if self._state is PlayerState.PLAYING:
            self._start_session(frame)
        else:
            self._teardown()
            self._resting_frame = frame
        self._emit_position(force=True)

    # -- settings -------------------------------------------------------------------------------

    def set_volume(self, volume: float) -> None:
        """Linear gain, 0..1."""
        self._volume = min(max(volume, 0.0), 1.0)
        if self._sink is not None:
            self._sink.setVolume(self._volume)

    def set_speed(self, speed: float) -> None:
        speed = min(max(speed, MIN_SPEED), MAX_SPEED)
        if speed != self._speed:
            self._restart_in_place(lambda: setattr(self, "_speed", speed))

    def set_loop(self, loop: Loop | None) -> None:
        self._restart_in_place(lambda: setattr(self, "_loop", loop))

    def set_channel_gains(self, gains: list[float] | None) -> None:
        """Scale each channel (e.g. ``[1, 0]`` mutes the right one). ``None`` restores unity gain."""
        wanted = tuple(gains) if gains is not None else None
        if wanted == self._gains:
            return

        def apply() -> None:
            self._gains = wanted
            self._pcm = self._encode()

        self._restart_in_place(apply)

    def set_output_device(self, device: QAudioDevice | None) -> None:
        self._restart_in_place(lambda: setattr(self, "_device", device))

    # -- internals ------------------------------------------------------------------------------

    def _restart_in_place(self, apply) -> None:
        """Change a setting that is baked into the sink, resuming from the same spot if playing."""
        was_playing = self._state is PlayerState.PLAYING
        frame = self._current_frame()
        if self._sink is not None:
            self._teardown()
        apply()
        self._resting_frame = frame
        if was_playing and self._clip is not None:
            self._start_session(frame)

    def _encode(self) -> bytes:
        if self._clip is None:
            return b""
        samples = self._clip.samples
        if self._gains is not None:
            samples = samples * np.asarray(self._gains, np.float32)[:, None]
        return encode_pcm(samples, SampleFormat.S16)

    def _loop_frames(self) -> tuple[int, int] | None:
        if self._loop is None or self._clip is None:
            return None
        rate = self._clip.sample_rate
        return int(self._loop.start * rate), int(self._loop.end * rate)

    def _loop_start_frame(self) -> int:
        span = self._loop_frames()
        return span[0] if span else 0

    def _start_session(self, frame: int) -> bool:
        assert self._clip is not None
        self._teardown()
        device = self._device or QMediaDevices.defaultAudioOutput()
        if device.isNull():
            self.errorOccurred.emit("No audio output device available")
            self._set_state(PlayerState.STOPPED)
            return False

        clip = self._clip
        self._session_rate = max(int(round(clip.sample_rate * self._speed)), 1)
        fmt = QAudioFormat()
        fmt.setSampleRate(self._session_rate)
        fmt.setChannelCount(clip.channels)
        fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)

        source = PcmSource(self._pcm, clip.channels * SampleFormat.S16.width)
        source.open_for_playback()
        source.seek_frame(frame)
        loop = self._loop_frames()
        source.set_loop(*loop) if loop else source.set_loop(None)

        sink = QAudioSink(device, fmt, self)
        sink.setVolume(self._volume)
        sink.stateChanged.connect(self._on_sink_state)
        sink.start(source)

        self._source, self._sink, self._session_start = source, sink, frame
        return True

    def _teardown(self) -> None:
        self._timer.stop()
        if self._sink is not None:
            self._sink.stateChanged.disconnect(self._on_sink_state)
            self._sink.stop()
            self._sink.deleteLater()
        if self._source is not None:
            self._source.close()
        self._sink = self._source = None

    def _current_frame(self) -> int:
        if self._clip is None:
            return 0
        if self._sink is None or self._state is PlayerState.STOPPED:
            return self._resting_frame
        played = int(self._sink.processedUSecs() * self._session_rate / 1_000_000)
        frame = self._session_start + played
        loop = self._loop_frames()
        if loop and self._session_start <= loop[1] and frame >= loop[1]:
            frame = loop[0] + (frame - loop[0]) % (loop[1] - loop[0])
        return min(frame, self._clip.frames)

    def _tick(self) -> None:
        self._emit_position()
        self._check_finished()

    def _on_sink_state(self, state: QAudio.State) -> None:
        if state == QAudio.State.IdleState:
            self._check_finished()

    def _check_finished(self) -> None:
        if self._state is not PlayerState.PLAYING or self._source is None or self._sink is None:
            return
        drained = self._sink.bytesFree() >= self._sink.bufferSize()
        if self._source.exhausted and (drained or self._sink.state() == QAudio.State.IdleState):
            self._teardown()
            assert self._clip is not None
            self._resting_frame = self._clip.frames
            self._set_state(PlayerState.STOPPED)
            self._emit_position(force=True)
            self.finished.emit()

    def _set_state(self, state: PlayerState) -> None:
        if state is not self._state:
            self._state = state
            self.stateChanged.emit(state)

    def _emit_position(self, force: bool = False) -> None:
        position = self.position
        if force or abs(position - self._last_emitted) > 1e-4:
            self._last_emitted = position
            self.positionChanged.emit(position)
