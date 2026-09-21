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
    dirty: bool = False  # edited since it was loaded or last saved
    undo: list[AudioClip] = field(default_factory=list, repr=False)
    redo: list[AudioClip] = field(default_factory=list, repr=False)


MAX_HISTORY = 10


class TakesModel(QObject):
    added = Signal(object)
    removed = Signal(object)
    renamed = Signal(object)
    clipChanged = Signal(object, str)  # take, label of the edit / undo / redo that changed it
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

    # -- editing history ------------------------------------------------------------------------

    def apply_edit(self, take: Take, clip: AudioClip, label: str) -> None:
        """Replace ``take``'s audio with the edited ``clip``, remembering the old one for undo."""
        take.undo.append(take.clip)
        del take.undo[
            :-MAX_HISTORY
        ]  # each version is a full copy of the audio, so the history is bounded
        take.redo.clear()
        take.clip, take.dirty = clip, True
        self.clipChanged.emit(take, label)

    def undo(self, take: Take) -> bool:
        if not take.undo:
            return False
        take.redo.append(take.clip)
        take.clip, take.dirty = take.undo.pop(), True
        self.clipChanged.emit(take, "Undo")
        return True

    def redo(self, take: Take) -> bool:
        if not take.redo:
            return False
        take.undo.append(take.clip)
        take.clip, take.dirty = take.redo.pop(), True
        self.clipChanged.emit(take, "Redo")
        return True

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
