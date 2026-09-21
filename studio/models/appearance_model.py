"""AppearanceModel: the single source of truth for how the waveforms look."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal

from audiowave import Appearance, Palette

CHANNELS = 2


class Target(Enum):
    """Which channel(s) an edit applies to."""

    LINKED = "linked"
    LEFT = "left"
    RIGHT = "right"


class AppearanceModel(QObject):
    """Holds one Appearance per channel and applies edits to the chosen target.

    In ``LINKED`` mode every edit goes to both channels, so they cannot drift apart unless the user
    deliberately switches to L or R. Views read from here; nothing else stores appearance state.
    """

    changed = Signal()

    def __init__(self, base: Appearance | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        base = base or Appearance()
        self._channels = [base] * CHANNELS
        self._target = Target.LINKED
        self._auto_gain = True

    # -- reading --------------------------------------------------------------------------------

    def appearance(self, channel: int = 0) -> Appearance:
        return self._channels[min(channel, CHANNELS - 1)]

    @property
    def target(self) -> Target:
        return self._target

    @property
    def editing(self) -> Appearance:
        """What the inspector shows: the target channel (channel 0 when linked)."""
        return self._channels[1] if self._target is Target.RIGHT else self._channels[0]

    @property
    def mixed(self) -> bool:
        """True when the two channels differ (only possible after editing one on its own)."""
        return self._channels[0] != self._channels[1]

    @property
    def auto_gain(self) -> bool:
        return self._auto_gain

    # -- editing --------------------------------------------------------------------------------

    def set_target(self, target: Target) -> None:
        if target is not self._target:
            self._target = target
            self.changed.emit()

    def set_auto_gain(self, enabled: bool) -> None:
        if enabled != self._auto_gain:
            self._auto_gain = enabled
            self.changed.emit()

    def update(self, **changes) -> None:
        self._apply(lambda a: a.with_(**changes))

    def update_palette(self, **colors: str) -> None:
        self._apply(lambda a: a.with_palette(**colors))

    def replace_all(self, appearance: Appearance) -> None:
        """Set both channels (presets, reset) and go back to linked editing."""
        self._channels = [appearance] * CHANNELS
        self._target = Target.LINKED
        self.changed.emit()

    def apply_palette(self, palette: Palette) -> None:
        """Swap colours on both channels (theme change) without touching shape settings."""
        self._channels = [a.with_(palette=palette) for a in self._channels]
        self.changed.emit()

    def _targets(self) -> list[int]:
        return {Target.LINKED: [0, 1], Target.LEFT: [0], Target.RIGHT: [1]}[self._target]

    def _apply(self, edit) -> None:
        new = list(self._channels)
        for index in self._targets():
            new[index] = edit(new[index])
        if new != self._channels:
            self._channels = new
            self.changed.emit()
