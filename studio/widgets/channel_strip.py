"""ChannelStrip: per-channel label, mute/solo and level meter, aligned with the waveform lanes."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtWidgets import QLabel, QToolButton, QWidget

from audiowave.widgets import LevelMeter, layout_lanes
from studio.theme import get_theme

CHANNEL_NAMES = ("L", "R")


def channel_gains(mutes: list[bool], solos: list[bool]) -> list[float]:
    """Per-channel playback gain: solo wins over mute, like a mixing desk."""
    if any(solos):
        return [1.0 if s else 0.0 for s in solos]
    return [0.0 if m else 1.0 for m in mutes]


class ChannelStrip(QWidget):
    """One column of controls per waveform lane, positioned with the same geometry function the waveform uses."""

    gainsChanged = Signal(object)  # list[float]

    WIDTH = 74

    def __init__(self, ruler_height: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedWidth(self.WIDTH)
        self._ruler = ruler_height
        self._channels = 0
        self._labels: list[QLabel] = []
        self._subs: list[QLabel] = []
        self._mutes: list[QToolButton] = []
        self._solos: list[QToolButton] = []
        self._meters: list[LevelMeter] = []

    def set_channels(self, count: int) -> None:
        for widget in [*self._labels, *self._subs, *self._mutes, *self._solos, *self._meters]:
            widget.deleteLater()
        self._labels, self._subs, self._mutes, self._solos, self._meters = [], [], [], [], []
        self._channels = count
        for i in range(count):
            name = CHANNEL_NAMES[i] if count == 2 and i < 2 else str(i + 1)
            label = QLabel(name, self)
            label.setObjectName("h2")
            sub = QLabel(f"CH {i + 1}", self)
            sub.setObjectName("dim")
            mute, solo = self._ms_button("M", "Mute"), self._ms_button("S", "Solo")
            meter = LevelMeter(Qt.Orientation.Vertical, parent=self)
            for w in (label, sub, mute, solo, meter):
                w.show()
            mute.toggled.connect(self._emit_gains)
            solo.toggled.connect(self._emit_gains)
            self._labels.append(label)
            self._subs.append(sub)
            self._mutes.append(mute)
            self._solos.append(solo)
            self._meters.append(meter)
        self.apply_theme()
        self._place()

    def _ms_button(self, text: str, tip: str) -> QToolButton:
        button = QToolButton(self)
        button.setProperty("kind", "ms")
        button.setText(text)
        button.setCheckable(True)
        button.setFixedSize(22, 18)
        button.setToolTip(tip)
        return button

    def set_levels(self, peaks: list[float]) -> None:
        for meter, peak in zip(self._meters, peaks, strict=False):
            meter.set_level(peak)

    def reset_levels(self) -> None:
        for meter in self._meters:
            meter.reset()

    def apply_theme(self) -> None:
        t = get_theme()
        for meter in self._meters:
            meter.set_colors(t.accent, "#ff8a1f", t.red, t.line, t.text)

    def _emit_gains(self) -> None:
        mutes = [b.isChecked() for b in self._mutes]
        solos = [b.isChecked() for b in self._solos]
        self.gainsChanged.emit(channel_gains(mutes, solos))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place()

    def _place(self) -> None:
        lanes: list[QRectF] = layout_lanes(self.width(), self.height(), self._channels, self._ruler)
        for i, lane in enumerate(lanes):
            top = int(lane.top()) + 8
            self._labels[i].setGeometry(10, top, 34, 28)
            self._subs[i].setGeometry(10, top + 26, 40, 14)
            self._mutes[i].move(10, top + 48)
            self._solos[i].move(10, top + 70)
            self._meters[i].setGeometry(self.WIDTH - 18, top, 8, max(int(lane.height()) - 16, 10))
