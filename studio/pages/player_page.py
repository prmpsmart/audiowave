"""Player page: overview, waveform / spectrogram / scope, transport and takes."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audiowave import AudioClip, Loop, Marker
from audiowave.audio import PlayerState
from audiowave.binding import bind_player
from audiowave.core import to_db
from audiowave.widgets import (
    OverviewView,
    SpectrogramView,
    VectorscopeView,
    Viewport,
    WaveformView,
)
from studio.session import Session
from studio.theme import get_theme, icon
from studio.widgets import Segmented, chip
from studio.widgets.channel_strip import ChannelStrip
from studio.widgets.takes_view import TakesView
from studio.widgets.transport import TransportBar

METER_WINDOW = 0.04  # seconds of audio behind the playhead that the meters look at


def volume_curve(slider: float) -> float:
    """Slider 0..100 to linear gain. Squared so the lower half is usable, like most players."""
    return (slider / 100.0) ** 2


class PlayerPage(QWidget):
    recordRequested = Signal()

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = session
        self._clip: AudioClip | None = None
        self._spectrogram_stale = True

        col = QVBoxLayout(self)
        col.setContentsMargins(22, 16, 22, 18)
        col.setSpacing(12)
        col.addLayout(self._info_row())

        self.overview = OverviewView(session.viewport)
        self.overview.setFixedHeight(58)
        col.addWidget(self.overview)
        col.addLayout(self._views_row(), 1)

        self.transport = TransportBar()
        col.addWidget(self.transport)
        col.addLayout(self._takes_header())
        self.takes_view = TakesView(session.takes)
        self.takes_view.newRecordingRequested.connect(self.recordRequested)
        col.addWidget(self.takes_view)

        self._wire()
        self._on_clip(session.clip)

    # -- construction ---------------------------------------------------------------------------

    def _info_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self._chips = [chip() for _ in range(5)]
        self._peak_chip = chip(accent=True)
        for c in (*self._chips, self._peak_chip):
            row.addWidget(c)
        row.addStretch()
        self.view_switch = Segmented(
            [
                ("waveform", "Waveform"),
                ("spectrogram", "Spectrogram"),
                ("scope", "Scope"),
            ]
        )
        self.view_switch.setFixedWidth(270)
        row.addWidget(self.view_switch)
        open_button = QPushButton("Open…")
        open_button.setIcon(icon("folder", get_theme().text))
        open_button.clicked.connect(self.open_dialog)
        row.addWidget(open_button)
        self._open_button = open_button
        return row

    def _views_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(0)
        vp: Viewport = self._s.viewport
        self.waveform = WaveformView(vp)
        self.spectrogram = SpectrogramView(vp)
        self.scope = VectorscopeView()
        self.strip = ChannelStrip(self.waveform.RULER_HEIGHT)
        self.stack = QStackedWidget()
        for w in (self.waveform, self.spectrogram, self.scope):
            self.stack.addWidget(w)
        well = QFrame()
        well.setObjectName("well")
        well_layout = QHBoxLayout(well)
        well_layout.setContentsMargins(0, 0, 0, 0)
        well_layout.setSpacing(0)
        well_layout.addWidget(self.strip)
        well_layout.addWidget(self.stack, 1)
        row.addWidget(well)
        return row

    def _takes_header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel("Takes")
        title.setObjectName("h3")
        hint = QLabel("Recordings land here. Click one to load it into the player.")
        hint.setObjectName("muted")
        self.save_button = QPushButton("Save WAV")
        self.export_button = QPushButton("Export PNG")
        for b in (self.save_button, self.export_button):
            b.setProperty("ghost", True)
        self.save_button.clicked.connect(self.save_wav)
        self.export_button.clicked.connect(self.export_png)
        row.addWidget(title)
        row.addSpacing(14)
        row.addWidget(hint)
        row.addStretch()
        row.addWidget(self.save_button)
        row.addWidget(self.export_button)
        return row

    # -- wiring ---------------------------------------------------------------------------------

    def _wire(self) -> None:
        s, tr = self._s, self.transport
        player = s.player

        bind_player(
            player,
            self.waveform,
            self.spectrogram,
            self.overview,
            sync_loop=False,
            follow=False,
        )
        player.positionChanged.connect(self.scope.set_position)
        player.positionChanged.connect(self._on_position)
        player.stateChanged.connect(self._on_state)

        s.clipChanged.connect(self._on_clip)
        s.loopChanged.connect(self._on_loop)
        s.loopEnabledChanged.connect(tr.loop.setChecked)
        s.markersChanged.connect(self._on_markers)
        s.appearance.changed.connect(self.apply_appearance)
        s.viewport.changed.connect(self._sync_zoom)

        for view in (self.waveform, self.spectrogram):
            view.loopChanged.connect(s.set_loop_region)

        tr.play.clicked.connect(player.toggle)
        tr.stop.clicked.connect(player.stop)
        tr.back.clicked.connect(lambda: player.seek(0))
        tr.record.clicked.connect(self.recordRequested)
        tr.loop.clicked.connect(s.set_loop_enabled)
        tr.marker.clicked.connect(lambda: s.add_marker(player.position))
        tr.speed.speedChanged.connect(player.set_speed)
        tr.volume.valueChanged.connect(lambda v: player.set_volume(volume_curve(v)))
        tr.volume.set_value(85)
        player.set_volume(volume_curve(85))
        tr.zoom.valueChanged.connect(self._on_zoom_slider)
        tr.follow.toggled.connect(lambda _: self._apply_follow())

        self.strip.gainsChanged.connect(player.set_channel_gains)
        self.view_switch.currentChanged.connect(self._on_view)
        self.apply_appearance()

    # -- state -> view --------------------------------------------------------------------------

    def apply_appearance(self) -> None:
        m = self._s.appearance
        self.waveform.set_appearance(m.appearance(0), 0)
        self.waveform.set_appearance(m.appearance(1), 1)
        self.waveform.set_auto_gain(m.auto_gain)
        self.overview.set_appearance(m.appearance(0))
        self.spectrogram.set_theme(m.appearance(0).palette)
        self.scope.set_theme(m.appearance(0).palette)
        self.strip.apply_theme()

    def _on_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self.waveform.set_clip(clip)
        self.overview.set_clip(clip, self.waveform.clip_peaks)
        self.scope.set_clip(clip)
        self._spectrogram_stale = True
        if self.stack.currentWidget() is self.spectrogram:
            self._ensure_spectrogram()
        self.strip.set_channels(clip.channels if clip else 0)
        self.strip.reset_levels()
        self._fill_info(clip)
        self.transport.set_time(0.0, clip.duration if clip else 0.0)
        for w in (self.transport, self.save_button, self.export_button):
            w.setEnabled(clip is not None)
        self._sync_zoom()

    def _fill_info(self, clip: AudioClip | None) -> None:
        if clip is None:
            for c in (*self._chips, self._peak_chip):
                c.setText("")
            return
        size_mb = clip.frames * clip.channels * 2 / 1_000_000
        channels = {1: "Mono", 2: "Stereo"}.get(clip.channels, f"{clip.channels} ch")
        for c, text in zip(
            self._chips,
            (
                f"{clip.sample_rate / 1000:g} kHz",
                channels,
                "PCM 16-bit",
                f"{clip.duration:.1f} s",
                f"{size_mb:.1f} MB",
            ),
            strict=True,
        ):
            c.setText(text)
        self._peak_chip.setText(f"peak {to_db(clip.peak()):.1f} dBFS")

    def _on_position(self, seconds: float) -> None:
        self.transport.set_time(seconds, self._s.player.duration)
        self.overview.set_position(seconds)
        clip = self._clip
        if clip is not None and self._s.player.state is PlayerState.PLAYING:
            end = int(seconds * clip.sample_rate)
            window = clip.samples[:, max(end - int(METER_WINDOW * clip.sample_rate), 0) : end]
            self.strip.set_levels([float(np.abs(c).max()) if c.size else 0.0 for c in window])

    def _on_state(self, state: PlayerState) -> None:
        self.transport.set_playing(state is PlayerState.PLAYING)
        self._apply_follow()
        if state is PlayerState.STOPPED:
            self.strip.reset_levels()

    def _apply_follow(self) -> None:
        on = self.transport.follow.isChecked() and self._s.player.state is PlayerState.PLAYING
        self.waveform.set_follow(on)
        self.spectrogram.set_follow(on)

    def _on_loop(self, loop: Loop | None) -> None:
        for view in (self.waveform, self.spectrogram, self.overview):
            view.set_loop(loop)

    def _on_markers(self, markers: list[Marker]) -> None:
        self.waveform.set_markers(markers)
        self.spectrogram.set_markers(markers)

    def _on_view(self, key: str) -> None:
        self.stack.setCurrentIndex({"waveform": 0, "spectrogram": 1, "scope": 2}[key])
        self.strip.setVisible(key == "waveform")
        if key == "spectrogram":
            self._ensure_spectrogram()

    def _ensure_spectrogram(self) -> None:
        """Analyse lazily: the FFT is only paid for if the user looks at it."""
        if self._spectrogram_stale and self._clip is not None:
            self.spectrogram.set_clip(self._clip)
            self._spectrogram_stale = False

    # -- zoom slider <-> viewport ---------------------------------------------------------------

    def _max_zoom(self) -> float:
        vp = self._s.viewport
        return max(vp.duration / Viewport.MIN_SPAN, 1.01) if vp.duration > 0 else 1.01

    def _on_zoom_slider(self, value: float) -> None:
        vp = self._s.viewport
        if vp.duration <= 0:
            return
        level = math.exp(value / 100 * math.log(self._max_zoom()))
        span = vp.duration / level
        pos = self._s.player.position
        centre = pos if vp.start <= pos <= vp.end else (vp.start + vp.end) / 2
        vp.set_range(centre - span / 2, centre + span / 2)

    def _sync_zoom(self) -> None:
        vp = self._s.viewport
        level = max(vp.zoom_level, 1.0)
        self.transport.zoom.set_value(math.log(level) / math.log(self._max_zoom()) * 100)
        self.transport.set_zoom_text(level)

    # -- file actions ---------------------------------------------------------------------------

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open audio", "", "WAV audio (*.wav)")
        if path:
            self._s.open_file(path)

    def save_wav(self) -> None:
        take = self._s.takes.current
        if take is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save WAV", f"{take.name}.wav", "WAV audio (*.wav)"
        )
        if path:
            self._s.save_take(take, Path(path))

    def export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export image", "waveform.png", "PNG image (*.png)"
        )
        if path:
            self.stack.currentWidget().grab().save(path)
            self._s.message.emit(f"Exported {Path(path).name}", False)

    def refresh_theme(self) -> None:
        self.transport.refresh_icons()
        self._open_button.setIcon(icon("folder", get_theme().text))
