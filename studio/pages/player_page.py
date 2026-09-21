"""Player page: overview, waveform / spectrogram / spectrum / scope / compare, edit tools, transport and takes."""

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
    QMenu,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audiowave import AudioClip, Loop, Loudness, Marker
from audiowave.audio import FILE_DIALOG_FILTER, PlayerState
from audiowave.binding import bind_player
from audiowave.core import to_db
from audiowave.widgets import (
    OverviewView,
    SpectrogramView,
    SpectrumView,
    VectorscopeView,
    Viewport,
    WaveformView,
)
from studio.session import Session
from studio.theme import get_theme, icon
from studio.widgets import Segmented, chip
from studio.widgets.channel_strip import ChannelStrip
from studio.widgets.compare_panel import ComparePanel, format_lufs
from studio.widgets.edit_bar import EditBar
from studio.widgets.takes_view import TakesView
from studio.widgets.transport import TransportBar

METER_WINDOW = 0.04  # seconds of audio behind the playhead that the meters look at
SPECTRUM_WINDOW = 2048  # samples analysed by the spectrum view
VIEWS = ("waveform", "spectrogram", "spectrum", "scope", "compare")


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
        col.setSpacing(10)
        col.addLayout(self._info_row())
        col.addLayout(self._tools_row())

        self.overview = OverviewView(session.viewport)
        self.overview.setFixedHeight(54)
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
        self._lufs_chip = chip(accent=True)
        self._lra_chip = chip()
        self._momentary_chip = chip()
        for c in (
            *self._chips,
            self._peak_chip,
            self._lufs_chip,
            self._lra_chip,
            self._momentary_chip,
        ):
            row.addWidget(c)
        row.addStretch()
        return row

    def _tools_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        self.edit_bar = EditBar()
        row.addWidget(self.edit_bar)
        row.addStretch()
        self.view_switch = Segmented(
            [
                ("waveform", "Waveform"),
                ("spectrogram", "Spectrogram"),
                ("spectrum", "Spectrum"),
                ("scope", "Scope"),
                ("compare", "Compare"),
            ]
        )
        self.view_switch.setFixedWidth(440)
        row.addWidget(self.view_switch)
        self._open_button = QPushButton("Open")
        self._open_button.setIcon(icon("folder", get_theme().text))
        self._open_menu = QMenu(self._open_button)
        self._open_menu.aboutToShow.connect(self._fill_open_menu)
        self._open_button.setMenu(self._open_menu)
        row.addWidget(self._open_button)
        return row

    def _views_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(0)
        vp: Viewport = self._s.viewport
        self.waveform = WaveformView(vp)
        self.spectrogram = SpectrogramView(vp)
        self.spectrum = SpectrumView()
        self.scope = VectorscopeView()
        self.compare = ComparePanel(self._s)
        self.strip = ChannelStrip(self.waveform.RULER_HEIGHT)
        self.stack = QStackedWidget()
        for w in (self.waveform, self.spectrogram, self.spectrum, self.scope, self.compare):
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
        hint = QLabel("Recordings and opened files land here. Click one to load it.")
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
            player, self.waveform, self.spectrogram, self.overview, sync_loop=False, follow=False
        )
        player.positionChanged.connect(self.scope.set_position)
        player.positionChanged.connect(self.compare.set_position)
        player.positionChanged.connect(self._on_position)
        player.stateChanged.connect(self._on_state)
        self.compare.seekRequested.connect(player.seek)

        s.clipChanged.connect(self._on_clip)
        s.loopChanged.connect(self._on_loop)
        s.loopEnabledChanged.connect(tr.loop.setChecked)
        s.markersChanged.connect(self._on_markers)
        s.silencesChanged.connect(self._on_silences)
        s.loudnessChanged.connect(self._on_loudness)
        s.appearance.changed.connect(self.apply_appearance)
        s.viewport.changed.connect(self._sync_zoom)
        s.busyChanged.connect(lambda _: self._update_edit_state())
        s.takes.clipChanged.connect(lambda *_: self._update_edit_state())
        s.takes.currentChanged.connect(lambda _t: self._update_edit_state())

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
        self.edit_bar.action.connect(self._on_edit_action)
        self.apply_appearance()
        self._update_edit_state()

    # -- editing --------------------------------------------------------------------------------

    def _on_edit_action(self, action: str, value: object) -> None:
        s = self._s
        if action == "undo":
            s.undo()
        elif action == "redo":
            s.redo()
        elif action == "find_silences":
            s.find_silences()
        elif action == "clear_silences":
            s.clear_silences()
        else:
            s.run_edit(action, value)  # type: ignore[arg-type]

    def _update_edit_state(self) -> None:
        take = self._s.takes.current
        selection = self._s.loop
        self.edit_bar.set_state(
            has_clip=take is not None,
            has_selection=selection is not None and selection.length > 0.01,
            can_undo=bool(take and take.undo),
            can_redo=bool(take and take.redo),
            busy=self._s.busy,
        )

    # -- state -> view --------------------------------------------------------------------------

    def apply_appearance(self) -> None:
        m = self._s.appearance
        self.waveform.set_appearance(m.appearance(0), 0)
        self.waveform.set_appearance(m.appearance(1), 1)
        self.waveform.set_auto_gain(m.auto_gain)
        self.overview.set_appearance(m.appearance(0))
        palette = m.appearance(0).palette
        for view in (self.spectrogram, self.spectrum, self.scope):
            view.set_theme(palette)
        self.compare.apply_appearance()
        self.strip.apply_theme()

    def _on_clip(self, clip: AudioClip | None) -> None:
        self._clip = clip
        self.waveform.set_clip(clip)
        self.overview.set_clip(clip, self.waveform.clip_peaks)
        self.scope.set_clip(clip)
        self.spectrum.clear()
        self._spectrogram_stale = True
        if self.stack.currentWidget() is self.spectrogram:
            self._ensure_spectrogram()
        if self.stack.currentWidget() is self.compare:
            self.compare.refresh()
        self.strip.set_channels(clip.channels if clip else 0)
        self.strip.reset_levels()
        self._fill_info(clip)
        self.transport.set_time(0.0, clip.duration if clip else 0.0)
        for w in (self.transport, self.save_button, self.export_button):
            w.setEnabled(clip is not None)
        self._sync_zoom()
        self._update_edit_state()

    def _fill_info(self, clip: AudioClip | None) -> None:
        if clip is None:
            for c in (
                *self._chips,
                self._peak_chip,
                self._lufs_chip,
                self._lra_chip,
                self._momentary_chip,
            ):
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
        self._peak_chip.setText(f"peak {to_db(clip.peak()):.1f} dBFS".replace("-", "−"))
        self._lufs_chip.setText("measuring loudness…")
        self._lra_chip.setText("")
        self._momentary_chip.setText("")

    def _on_loudness(self, loudness: Loudness | None) -> None:
        if loudness is None:
            return
        self._lufs_chip.setText(format_lufs(loudness.integrated))
        self._lra_chip.setText(
            f"LRA {loudness.range:.1f} LU" if math.isfinite(loudness.integrated) else ""
        )
        self._update_momentary(self._s.player.position)

    def _update_momentary(self, seconds: float) -> None:
        loudness = self._s.loudness
        if loudness is None:
            return
        value = loudness.momentary_at(seconds)
        self._momentary_chip.setText(
            f"M {value:.1f}".replace("-", "−") if math.isfinite(value) else "M −∞"
        )

    def _on_position(self, seconds: float) -> None:
        self.transport.set_time(seconds, self._s.player.duration)
        self.overview.set_position(seconds)
        self._update_momentary(seconds)
        clip = self._clip
        if clip is None:
            return
        end = int(seconds * clip.sample_rate)
        playing = self._s.player.state is PlayerState.PLAYING
        if playing:
            window = clip.samples[:, max(end - int(METER_WINDOW * clip.sample_rate), 0) : end]
            self.strip.set_levels([float(np.abs(c).max()) if c.size else 0.0 for c in window])
        if self.stack.currentWidget() is self.spectrum:
            mono = clip.samples[:, max(end - SPECTRUM_WINDOW, 0) : end].mean(axis=0)
            self.spectrum.feed(mono, clip.sample_rate)

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
        self._update_edit_state()

    def _on_markers(self, markers: list[Marker]) -> None:
        self.waveform.set_markers(markers)
        self.spectrogram.set_markers(markers)

    def _on_silences(self, silences: list[Loop]) -> None:
        self.waveform.set_highlights(silences)
        self.spectrogram.set_highlights(silences)

    def _on_view(self, key: str) -> None:
        leaving_compare = self.stack.currentWidget() is self.compare and key != "compare"
        if leaving_compare:
            self.compare.restore_a()
            self._s.viewport.set_duration(self._clip.duration if self._clip else 0.0)
        self.stack.setCurrentIndex(VIEWS.index(key))
        self.strip.setVisible(key == "waveform")
        self.overview.setVisible(key != "compare")
        if key == "spectrogram":
            self._ensure_spectrogram()
        elif key == "compare":
            self.compare.refresh()
        elif key == "spectrum":
            self._on_position(self._s.player.position)

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

    def _fill_open_menu(self) -> None:
        menu = self._open_menu
        menu.clear()
        menu.addAction("Browse…", self.open_dialog)
        recent = self._s.recent
        paths = recent.paths() if recent is not None else []
        if paths:
            menu.addSeparator()
            for path in paths:
                menu.addAction(path.name, lambda p=path: self._s.open_file(p)).setToolTip(str(path))
            menu.addSeparator()
            menu.addAction("Clear recent", recent.clear)  # type: ignore[union-attr]

    def open_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open audio", "", FILE_DIALOG_FILTER)
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
        self.edit_bar.refresh_icons()
        self._open_button.setIcon(icon("folder", get_theme().text))
