"""The active theme, for custom-painted widgets that cannot get their colours from the stylesheet."""

from __future__ import annotations

from .tokens import DARK, Theme

_current: Theme = DARK


def get_theme() -> Theme:
    return _current


def set_theme(theme: Theme) -> None:
    global _current
    _current = theme
