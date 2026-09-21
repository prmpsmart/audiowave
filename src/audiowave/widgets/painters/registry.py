"""Name -> painter lookup. Adding a style means writing a class and decorating it with ``@register``."""

from __future__ import annotations

from .base import WavePainter

_PAINTERS: dict[str, WavePainter] = {}
DEFAULT_STYLE = "bars"


def register(cls: type[WavePainter]) -> type[WavePainter]:
    """Class decorator: instantiate ``cls`` and make it available under ``cls.name``."""
    if cls.name in _PAINTERS:
        raise ValueError(f"a painter named {cls.name!r} is already registered")
    _PAINTERS[cls.name] = cls()
    return cls


def get_painter(name: str) -> WavePainter:
    """The painter for ``name``; unknown names fall back to the default so old presets still render."""
    return _PAINTERS.get(name) or _PAINTERS[DEFAULT_STYLE]


def painter_names() -> list[str]:
    return list(_PAINTERS)


def painters() -> list[WavePainter]:
    return list(_PAINTERS.values())
