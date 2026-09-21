"""Recently opened files, remembered between runs."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

_KEY = "recent_files"


class RecentFiles:
    """Newest first, unique, capped. Files that no longer exist are dropped when listed."""

    def __init__(self, settings: QSettings, limit: int = 10) -> None:
        self._settings, self._limit = settings, limit

    def paths(self) -> list[Path]:
        stored = self._settings.value(_KEY, [], type=list)
        return [Path(p) for p in stored if Path(p).is_file()]

    def add(self, path: str | Path) -> None:
        resolved = str(Path(path).resolve())
        stored = [p for p in self._settings.value(_KEY, [], type=list) if p != resolved]
        self._settings.setValue(_KEY, [resolved, *stored][: self._limit])
        self._settings.sync()

    def clear(self) -> None:
        self._settings.remove(_KEY)
        self._settings.sync()
