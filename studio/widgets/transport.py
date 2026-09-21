"""TransportBar: time readout, transport buttons and playback sliders."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from studio.theme import get_theme

from .kit import IconButton, LabeledSlider, Toggle

SPEEDS = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)


def split_time(seconds: float) -> tuple[str, str]:
    """``(main, fraction)`` for the big readout, e.g. ``("01:42", ".318")``."""
    seconds = max(seconds, 0.0)
    whole = int(seconds)
    millis = round((seconds - whole) * 1000)
    if millis == 1000:
        whole, millis = whole + 1, 0
    h, rem = divmod(whole, 3600)
    m, s = divmod(rem, 60)
    main = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    return main, f".{millis:03d}"


class SpeedButton(QToolButton):
    """``1.0×`` pill that opens a menu of playback speeds."""

    speedChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("kind", "pill")
        self.setFixedHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Playback speed")
        self._speed = 1.0
        self._sync_text()
        self.clicked.connect(self._open_menu)

    def set_speed(self, speed: float) -> None:
        self._speed = speed
        self._sync_text()

    def _sync_text(self) -> None:
        self.setText(f"{self._speed:g}×")

    def _open_menu(self) -> None:
        menu = QMenu(self)
        for speed in SPEEDS:
            action = menu.addAction(f"{speed:g}×")
            action.setCheckable(True)
            action.setChecked(speed == self._speed)
            action.triggered.connect(lambda _=False, s=speed: self._choose(s))
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _choose(self, speed: float) -> None:
        self.set_speed(speed)
        self.speedChanged.emit(speed)


class TransportBar(QFrame):
    """Purely presentational: exposes buttons and sliders; the page decides what they do."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 12, 20, 12)
        row.setSpacing(26)

        row.addLayout(self._time_block())
        row.addStretch(1)
        row.addLayout(self._buttons())
        row.addStretch(1)
        row.addWidget(self._sliders())

    def _time_block(self) -> QVBoxLayout:
        col = QVBoxLayout()
        col.setSpacing(2)
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
        self._sub = QLabel("")
        self._sub.setObjectName("subtime")
        col.addLayout(big)
        col.addWidget(self._sub)
        return col

    def _buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self.back = IconButton("back", tooltip="Back to start", size=42)
        self.record = IconButton("rec", kind="record", role="red", tooltip="Record a new take")
        self.play = IconButton(
            "play",
            kind="play",
            size=62,
            icon_size=26,
            role="on_accent",
            tooltip="Play / pause (Space)",
        )
        self.stop = IconButton("stop", tooltip="Stop")
        self.loop = IconButton(
            "loop",
            kind="toggle",
            role="muted",
            checked_role="teal",
            checkable=True,
            tooltip="Loop the selected region (drag on the ruler to select)",
        )
        self.marker = IconButton(
            "flag",
            kind="small",
            size=34,
            icon_size=15,
            tooltip="Add marker at playhead (M)",
        )
        self.speed = SpeedButton()
        for w in (
            self.back,
            self.record,
            self.play,
            self.stop,
            self.loop,
            self.marker,
            self.speed,
        ):
            row.addWidget(w)
        return row

    def _sliders(self) -> QWidget:
        box = QWidget()
        box.setFixedWidth(250)
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(9)
        self.volume = LabeledSlider("Volume", 0, 100, 1, lambda v: f"{v:.0f}%")
        self.zoom = LabeledSlider("Zoom", 0, 100, 1, lambda v: "")
        self.zoom_label = QLabel("1.0×")
        self.zoom_label.setObjectName("value")
        self.follow = Toggle(True)
        follow_row = QHBoxLayout()
        follow_row.setContentsMargins(0, 0, 0, 0)
        follow_label = QLabel("Follow playhead")
        follow_label.setObjectName("muted")
        follow_row.addWidget(follow_label)
        follow_row.addStretch()
        follow_row.addWidget(self.follow)
        col.addWidget(self.volume)
        col.addWidget(self.zoom)
        col.addLayout(follow_row)
        return box

    # -- presentation ---------------------------------------------------------------------------

    def set_time(self, position: float, duration: float) -> None:
        main, frac = split_time(position)
        self._main.setText(main)
        self._frac.setText(frac)
        left_main, left_frac = split_time(max(duration - position, 0))
        total_main, total_frac = split_time(duration)
        self._sub.setText(f"−{left_main}{left_frac[:2]} left    {total_main}{total_frac[:2]} total")

    def set_playing(self, playing: bool) -> None:
        self.play.set_icon_name("pause" if playing else "play")

    def set_zoom_text(self, level: float) -> None:
        self.zoom._value.setText(f"{level:.1f}×" if level < 100 else f"{level:.0f}×")

    def refresh_icons(self) -> None:
        for button in self.findChildren(IconButton):
            button.refresh(get_theme())

    def sizeHint(self) -> QSize:
        return QSize(900, 92)
