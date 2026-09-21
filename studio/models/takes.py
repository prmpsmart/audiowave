"""Takes: recorded or opened clips the user can switch between."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from audiowave import AudioClip


@dataclass(eq=False)
class Take:
    id: int
    name: str
    clip: AudioClip
    created: datetime = field(default_factory=datetime.now)
    path: Path | None = None


class TakesModel(QObject):
    added = Signal(object)
    removed = Signal(object)
    renamed = Signal(object)
    currentChanged = Signal(object)  # Take | None

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._takes: list[Take] = []
        self._current: Take | None = None
        self._next_id = 1

    def __iter__(self):
        return iter(self._takes)

    def __len__(self) -> int:
        return len(self._takes)

    @property
    def current(self) -> Take | None:
        return self._current

    def add(
        self,
        clip: AudioClip,
        name: str | None = None,
        path: Path | None = None,
        select: bool = True,
    ) -> Take:
        take = Take(self._next_id, name or f"Take {self._next_id}", clip, path=path)
        self._next_id += 1
        self._takes.append(take)
        self.added.emit(take)
        if select:
            self.set_current(take)
        return take

    def set_current(self, take: Take | None) -> None:
        if take is not self._current:
            self._current = take
            self.currentChanged.emit(take)

    def rename(self, take: Take, name: str) -> None:
        name = name.strip()
        if name and name != take.name:
            take.name = name
            self.renamed.emit(take)

    def remove(self, take: Take) -> None:
        if take not in self._takes:
            return
        index = self._takes.index(take)
        self._takes.remove(take)
        self.removed.emit(take)
        if take is self._current:
            self.set_current(self._takes[min(index, len(self._takes) - 1)] if self._takes else None)
