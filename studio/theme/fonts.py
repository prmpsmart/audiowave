"""Bundled fonts (SIL OFL), with system fallbacks if loading fails."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtGui import QFontDatabase

FONT_DIR = Path(__file__).resolve().parent.parent / "resources" / "fonts"


@dataclass(frozen=True)
class Fonts:
    serif: str  # display headings
    sans: str  # UI text
    mono: str  # every number


def load_fonts() -> Fonts:
    """Register the bundled fonts and return the family names to use."""
    for path in sorted(FONT_DIR.glob("*.ttf")):
        QFontDatabase.addApplicationFont(str(path))
    families = set(QFontDatabase.families())

    def pick(wanted: str, *fallbacks: str) -> str:
        return next((f for f in (wanted, *fallbacks) if f in families), fallbacks[-1] if fallbacks else wanted)

    return Fonts(
        serif=pick("Instrument Serif", "Georgia", "Times New Roman"),
        sans=pick("Hanken Grotesk", "Helvetica Neue", "Segoe UI", "Arial"),
        mono=pick("DM Mono", "Menlo", "Consolas", "Courier New"),
    )
