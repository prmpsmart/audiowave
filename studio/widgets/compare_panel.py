"""ComparePanel: two takes stacked on one shared timeline, with a listen switch and a loudness difference."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from audiowave import AudioClip, Loudness
from audiowave.audio import FILE_DIALOG_FILTER, PlayerState
from audiowave.widgets import WaveformView
from studio.models import Take
from studio.session import Session

from .kit import Segmented


def format_lufs(value: float) -> str:
    return "−∞ LUFS" if not math.isfinite(value) else f"{value:.1f} LUFS".replace("-", "−")


class ComparePanel(QWidget):
    """A is the current take; B is chosen here. Both draw as a mono mix over the session's viewport,
    and the *Listen* switch decides which of them the player plays (keeping the position), so
    switching between A and B while playing is instant and level-matched by eye and by LUFS."""

    seekRequested = Signal(float)

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._s = session
        self._b: Take | None = None
        self._listening = "a"
        self._loud: dict[str, Loudness | None] = {"a": None, "b": None}

        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        col.addLayout(self._header())
        self._label_a = QLabel()
        self._label_b = QLabel()
        for label in (self._label_a, self._label_b):
            label.setObjectName("muted")
        self.wave_a, self.wave_b = WaveformView(session.viewport), WaveformView(session.viewport)
        for view in (self.wave_a, self.wave_b):
            view.seekRequested.connect(self.seekRequested)
        self.wave_b.set_ruler_visible(False)
        col.addWidget(self._label_a)
        col.addWidget(self.wave_a, 1)
        col.addWidget(self._label_b)
        col.addWidget(self.wave_b, 1)

        # Only rebuild while visible: refreshing touches the shared viewport, which belongs to whichever view is showing.
        session.takes.added.connect(lambda _t: self.isVisible() and self.refresh())
        session.takes.removed.connect(lambda _t: self.isVisible() and self.refresh())
        session.takes.renamed.connect(lambda _t: self._update_labels())

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(10)
        title = QLabel("Compare")
        title.setObjectName("h3")
        with_label = QLabel("with")
        with_label.setObjectName("muted")
        self.combo = QComboBox()
        self.combo.setMinimumWidth(200)
        self.combo.currentIndexChanged.connect(self._on_choice)
        self.add_button = QPushButton("Add file…")
        self.add_button.clicked.connect(self._add_file)
        self.listen = Segmented([("a", "Listen A"), ("b", "Listen B")])
        self.listen.setFixedWidth(200)
        self.listen.currentChanged.connect(self._on_listen)
        self.delta = QLabel()
        self.delta.setObjectName("mono")
        for w in (title, with_label, self.combo, self.add_button):
            row.addWidget(w)
        row.addStretch()
        row.addWidget(self.delta)
        row.addWidget(self.listen)
        return row

    # -- data -----------------------------------------------------------------------------------

    @property
    def other(self) -> Take | None:
        return self._b

    def refresh(self) -> None:
        """Rebuild the choice of B from the takes (everything except the current one) and redraw."""
        current = self._s.takes.current
        others = [t for t in self._s.takes if t is not current]
        self.combo.blockSignals(True)
        self.combo.clear()
        for take in others:
            self.combo.addItem(take.name, take)
        keep = self._b if self._b in others else (others[-1] if others else None)
        self.combo.setCurrentIndex(others.index(keep) if keep else -1)
        self.combo.blockSignals(False)
        self._b = keep
        self.listen.set_enabled_keys({"a", "b"} if keep else {"a"})
        self._show_clips()

    def _on_choice(self, index: int) -> None:
        self._b = self.combo.itemData(index) if index >= 0 else None
        self._show_clips()

    def _show_clips(self) -> None:
        a = self._s.clip
        b = self._b.clip if self._b else None
        self._loud = {"a": None, "b": None}
        self.wave_a.set_clip(a.to_mono() if a else None, reset_viewport=False)
        self.wave_b.set_clip(b.to_mono() if b else None, reset_viewport=False)
        longest = max((c.duration for c in (a, b) if c), default=0.0)
        self._s.viewport.set_duration(longest)
        for key, clip in (("a", a), ("b", b)):
            if clip is not None:
                self._s.loudness_of(
                    clip, lambda result, k=key, c=clip: self._on_loudness(k, c, result)
                )
        self._update_labels()
        if self._listening == "b" and b is None:
            self.listen.set_current("a", emit=True)

    def _on_loudness(self, key: str, clip: AudioClip, result: Loudness) -> None:
        expected = self._s.clip if key == "a" else (self._b.clip if self._b else None)
        if clip is expected:
            self._loud[key] = result
            self._update_labels()

    def _update_labels(self) -> None:
        a_take, b_take = self._s.takes.current, self._b
        for label, key, take in ((self._label_a, "a", a_take), (self._label_b, "b", b_take)):
            loudness = self._loud[key]
            reading = format_lufs(loudness.integrated) if loudness else "measuring…"
            label.setText(
                f"{key.upper()} · {take.name}   {reading}"
                if take
                else f"{key.upper()} · choose a take"
            )
        a, b = self._loud["a"], self._loud["b"]
        if a and b and math.isfinite(a.integrated) and math.isfinite(b.integrated):
            self.delta.setText(f"B is {b.integrated - a.integrated:+.1f} LU".replace("-", "−"))
        else:
            self.delta.setText("")

    def _add_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Add a file to compare", "", FILE_DIALOG_FILTER)
        if path:
            self._s.open_file(Path(path), select=False)

    # -- playback -------------------------------------------------------------------------------

    def _on_listen(self, key: str) -> None:
        self._listening = key
        self.play_selected()

    def play_selected(self) -> None:
        """Load whichever take is being listened to into the player, keeping position and play state."""
        clip = self._s.clip if self._listening == "a" else (self._b.clip if self._b else None)
        if clip is None:
            return
        player = self._s.player
        position, playing = player.position, player.state is PlayerState.PLAYING
        player.load(clip)
        player.seek(min(position, clip.duration))
        if playing:
            player.play()

    def restore_a(self) -> None:
        """Leave compare mode: make sure the player holds the current take again."""
        if self._listening == "b":
            self.listen.set_current("a", emit=True)

    def set_position(self, seconds: float) -> None:
        self.wave_a.set_position(seconds)
        self.wave_b.set_position(seconds)

    def apply_appearance(self) -> None:
        a = self._s.appearance.appearance(0)
        for view in (self.wave_a, self.wave_b):
            view.set_appearance(a)
            view.set_auto_gain(self._s.appearance.auto_gain)
