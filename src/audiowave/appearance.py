"""Value objects describing how a waveform looks. Qt-free so presets can be stored as plain JSON."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Gravity(Enum):
    """Which part of each bucket's min/max span is drawn."""

    AVERAGE = "average"  # symmetric bar of half the peak-to-peak span
    MIN_MAX = "min_max"  # peaks above the midline, troughs below
    MIN = "min"  # troughs only
    MAX = "max"  # peaks only


@dataclass(frozen=True)
class Palette:
    """Colours as ``#rrggbb`` strings."""

    played: str = "#ffb238"
    unplayed: str = "#4a4d43"
    playhead: str = "#ece6d6"
    background: str = "#0d0e0c"
    grid: str = "#252821"
    loop: str = "#59d3c2"
    marker: str = "#ff8a1f"
    text: str = "#8a8f7d"

    def with_(self, **changes: str) -> Palette:
        return dataclasses.replace(self, **changes)


@dataclass(frozen=True)
class Appearance:
    """Everything a painter needs besides the data. Immutable: derive variants with :meth:`with_`."""

    style: str = "bars"
    gravity: Gravity = Gravity.MIN_MAX
    bar_width: float = 3.0
    bar_spacing: float = 2.0
    radius: float = 1.0
    scale: float = 0.92
    idle_height: float = 2.0
    show_midline: bool = True
    show_grid: bool = True
    playhead_radius: float = 6.0
    palette: Palette = field(default_factory=Palette)

    def with_(self, **changes: Any) -> Appearance:
        return dataclasses.replace(self, **changes)

    def with_palette(self, **changes: str) -> Appearance:
        return dataclasses.replace(self, palette=self.palette.with_(**changes))

    # -- (de)serialisation for presets ----------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        data = dataclasses.asdict(self)
        data["gravity"] = self.gravity.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Appearance:
        """Build from a dict, ignoring unknown keys so older/newer presets still load."""
        known = {f.name for f in dataclasses.fields(cls)}
        values = {k: v for k, v in data.items() if k in known}
        if "gravity" in values:
            values["gravity"] = Gravity(values["gravity"])
        palette = values.pop("palette", None)
        if isinstance(palette, dict):
            pknown = {f.name for f in dataclasses.fields(Palette)}
            values["palette"] = Palette(**{k: v for k, v in palette.items() if k in pknown})
        return cls(**values)
