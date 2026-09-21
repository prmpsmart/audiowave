"""Design tokens. Every colour in the app comes from here, so a theme is one object."""

from __future__ import annotations

from dataclasses import dataclass

from audiowave import Palette


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    surface: str
    surface2: str
    line: str
    line2: str
    text: str
    muted: str
    dim: str
    accent: str
    on_accent: str
    teal: str
    red: str
    waveform: Palette

    @property
    def is_dark(self) -> bool:
        return self.name == "dark"


DARK = Theme(
    name="dark",
    bg="#0b0c0a",
    surface="#121411",
    surface2="#181a16",
    line="#252821",
    line2="#33372d",
    text="#ece6d6",
    muted="#8a8f7d",
    dim="#575c4f",
    accent="#ffb238",
    on_accent="#1a1305",
    teal="#59d3c2",
    red="#ff4b3a",
    waveform=Palette(),
)

LIGHT = Theme(
    name="light",
    bg="#f3f0e6",
    surface="#faf8f2",
    surface2="#ede9dd",
    line="#dbd6c5",
    line2="#c7c1ad",
    text="#1d1c17",
    muted="#6c6858",
    dim="#a29d89",
    accent="#e08a00",
    on_accent="#ffffff",
    teal="#178576",
    red="#d63a2a",
    waveform=Palette(
        played="#e08a00",
        unplayed="#b8b29a",
        playhead="#1d1c17",
        background="#faf8f2",
        grid="#e4dfcf",
        loop="#178576",
        marker="#c4610f",
        text="#6c6858",
    ),
)

THEMES = {t.name: t for t in (DARK, LIGHT)}
