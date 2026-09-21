"""Named appearance presets stored as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from audiowave import Appearance


class PresetStore:
    """A small JSON file of ``{name: appearance dict}``. Missing or corrupt files read as empty."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def names(self) -> list[str]:
        return sorted(self._read())

    def load(self, name: str) -> Appearance | None:
        data = self._read().get(name)
        return Appearance.from_dict(data) if data else None

    def save(self, name: str, appearance: Appearance) -> None:
        data = self._read()
        data[name] = appearance.to_dict()
        self._write(data)

    def delete(self, name: str) -> None:
        data = self._read()
        if data.pop(name, None) is not None:
            self._write(data)

    def _read(self) -> dict[str, dict]:
        try:
            data = json.loads(self._path.read_text())
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write(self, data: dict) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._path)  # atomic: a crash never leaves half a file
