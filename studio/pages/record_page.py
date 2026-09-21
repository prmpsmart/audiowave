"""Record page: capture from an input device with a live waveform, then hand the result over as a take."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from audiowave import LivePeaks
from audiowave.audio import RecorderState, request_microphone
from audiowave.widgets import LevelMeter, LiveWaveformView, SpectrumView
from studio.models import Take
from studio.session import Session
from studio.theme import get_theme
from studio.widgets import IconButton, Segmented, chip, set_property
from studio.widgets.transport import split_time

VISIBLE_SECONDS = 8.0  # how much history the live waveform shows before it scrolls


class RecordPage(QWidget):
    recorded = Signal(object)  # Take

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = session
        self._live: LivePeaks | None = None
        self._tail = np.zeros(0, np.float32)  # the last few thousand samples, for the spectrum
        rec = session.recorder

        col = QVBoxLayout(self)
        col.setContentsMargins(22, 16, 22, 18)
        col.setSpacing(14)
        col.addLayout(self._settings_row())

        well = QFrame()
        well.setObjectName("well")
        well_row = QHBoxLayout(well)
        well_row.setContentsMargins(12, 12, 12, 12)
        well_row.setSpacing(12)
        self._meters = [LevelMeter(Qt.Orientation.Vertical) for _ in range(2)]
        meters = QHBoxLayout()
        meters.setSpacing(4)
        for m in self._meters:
            m.setFixedWidth(9)
            meters.addWidget(m)
        well_row.addLayout(meters)
        self.live_view = LiveWaveformView()
        self.live_view.setMinimumHeight(240)
        well_row.addWidget(self.live_view, 1)
        col.addWidget(well, 3)

        spectrum_well = QFrame()
        spectrum_well.setObjectName("well")
        spectrum_layout = QVBoxLayout(spectrum_well)
        spectrum_layout.setContentsMargins(6, 6, 6, 6)
        self.spectrum = SpectrumView()
        self.spectrum.setMinimumHeight(140)
        spectrum_layout.addWidget(self.spectrum)
        col.addWidget(spectrum_well, 2)

        col.addWidget(self._control_card())

        rec.chunkReady.connect(self._on_chunk)
        rec.levelChanged.connect(self._on_level)
        rec.elapsedChanged.connect(self._on_elapsed)
        rec.stateChanged.connect(self._on_state)
        session.appearance.changed.connect(self.apply_appearance)
        self.apply_appearance()
        self._on_state(RecorderState.STOPPED)

    # -- construction ---------------------------------------------------------------------------

    def _settings_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        title = QLabel("Record")
        title.setObjectName("h1")
        row.addWidget(title)
        row.addStretch()
        self.channels = Segmented([("1", "Mono"), ("2", "Stereo")])
        self.rate = Segmented([("44100", "44.1 kHz"), ("48000", "48 kHz")])
        for seg in (self.channels, self.rate):
            seg.setFixedWidth(170)
            row.addWidget(seg)
        self._format_chip = chip()
        row.addWidget(self._format_chip)
        return row

    def _control_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        row = QHBoxLayout(card)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(26)

        time_col = QVBoxLayout()
        time_col.setSpacing(2)
        big = QHBoxLayout()
        big.setSpacing(0)
        self._main = QLabel("00:00")
        self._main.setObjectName("bigtime")
        self._frac = QLabel(".000")
        self._frac.setObjectName("bigtime_frac")
        self._frac.setAlignment(Qt.AlignmentFlag.AlignBottom)
        big.addWidget(self._main)
        big.addWidget(self._frac)
        big.addStretch()
        self._status = QLabel("Ready")
        self._status.setObjectName("subtime")
        time_col.addLayout(big)
        time_col.addWidget(self._status)
        row.addLayout(time_col)
        row.addStretch(1)

        self.pause_button = IconButton("pause", tooltip="Pause / resume")
        self.record_button = IconButton(
            "rec",
            kind="recbig",
            size=62,
            icon_size=26,
            role="text",
            tooltip="Start / stop recording (R)",
        )
        self.stop_button = IconButton("stop", tooltip="Stop and keep the take")
        for b in (self.pause_button, self.record_button, self.stop_button):
            row.addWidget(b)
        row.addStretch(1)
        hint = QLabel(
            "Input device is chosen in the top bar.\nA finished recording becomes a take."
        )
        hint.setObjectName("muted")
        row.addWidget(hint)

        self.record_button.clicked.connect(self.toggle_recording)
        self.stop_button.clicked.connect(self.stop)
        self.pause_button.clicked.connect(self._toggle_pause)
        return card

    # -- actions --------------------------------------------------------------------------------

    def toggle_recording(self) -> None:
        if self._s.recorder.state is RecorderState.STOPPED:
            self.start()
        else:
            self.stop()

    def start(self) -> None:
        request_microphone(self, self._start_after_permission)

    def _start_after_permission(self, granted: bool) -> None:
        if not granted:
            self._s.message.emit(
                "Microphone access was denied. Allow it in System Settings → Privacy.",
                True,
            )
            return
        device = self._s.input_device.native if self._s.input_device else None
        rec = self._s.recorder
        if (
            not rec.start(int(self.rate.current), int(self.channels.current), device)
            or rec.format is None
        ):
            return
        spb = max(
            int(
                rec.format.sample_rate
                * VISIBLE_SECONDS
                / max(self.live_view.buckets_for_width(), 1)
            ),
            64,
        )
        self._live = LivePeaks(rec.format.channels, spb)
        self.live_view.set_source(self._live)
        self._format_chip.setText(
            f"{rec.format.sample_rate / 1000:g} kHz · {rec.format.channels} ch"
        )

    def stop(self) -> None:
        clip = self._s.recorder.stop()
        if clip is not None:
            take: Take = self._s.takes.add(clip)
            self._s.message.emit(f"Saved {take.name} ({clip.duration:.1f} s)", False)
            self.recorded.emit(take)

    def _toggle_pause(self) -> None:
        rec = self._s.recorder
        rec.resume() if rec.state is RecorderState.PAUSED else rec.pause()

    # -- recorder -> view -----------------------------------------------------------------------

    def _on_chunk(self, samples) -> None:
        if self._live is not None:
            self._live.append(samples)
            self.live_view.refresh()
        rate = self._s.recorder.format.sample_rate if self._s.recorder.format else 44100
        self._tail = np.concatenate([self._tail, samples.mean(axis=0)])[-4096:]
        self.spectrum.feed(self._tail, rate)

    def _on_level(self, peaks: list[float]) -> None:
        for meter, peak in zip(self._meters, peaks, strict=False):
            meter.set_level(peak)

    def _on_elapsed(self, seconds: float) -> None:
        main, frac = split_time(seconds)
        self._main.setText(main)
        self._frac.setText(frac)

    def _on_state(self, state: RecorderState) -> None:
        recording = state is RecorderState.RECORDING
        idle = state is RecorderState.STOPPED
        self._status.setText(
            {"stopped": "Ready", "recording": "Recording…", "paused": "Paused"}[state.value]
        )
        self.record_button.set_icon_name(
            "stop" if recording or state is RecorderState.PAUSED else "rec"
        )
        self.pause_button.set_icon_name("play" if state is RecorderState.PAUSED else "pause")
        self.pause_button.setEnabled(not idle)
        self.stop_button.setEnabled(not idle)
        self.channels.setEnabled(idle)
        self.rate.setEnabled(idle)
        self.live_view.set_head_color(get_theme().red if recording else None)
        set_property(self._status, "recording", recording)
        if idle:
            for meter in self._meters:
                meter.reset()
            self.spectrum.clear()
            self._tail = np.zeros(0, np.float32)
        if idle and self._live is None:
            self._on_elapsed(0.0)

    def apply_appearance(self) -> None:
        a = self._s.appearance.appearance(0)
        self.live_view.set_appearance(a.with_(show_grid=False))
        self.spectrum.set_theme(a.palette)
        t = get_theme()
        for meter in self._meters:
            meter.set_colors(t.accent, "#ff8a1f", t.red, t.line, t.text)

    def refresh_theme(self) -> None:
        for button in self.findChildren(IconButton):
            button.refresh(get_theme())
        self.apply_appearance()
