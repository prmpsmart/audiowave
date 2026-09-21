"""FrameLogModel: the "Frame | Size | Time | Level" table, newest first."""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

COLUMNS = ("Frame", "Size", "Time", "Level")
LEVEL_ROLE = Qt.ItemDataRole.UserRole


class FrameLogModel(QAbstractTableModel):
    def __init__(self, max_rows: int = 200, parent=None) -> None:
        super().__init__(parent)
        self._rows: deque[tuple[int, int, float, float]] = deque(maxlen=max_rows)
        self._max = max_rows

    def add(self, index: int, size: int, time: float, level: float) -> None:
        self.beginInsertRows(QModelIndex(), 0, 0)
        if len(self._rows) == self._max:  # keep the model's row count in step with the deque cap
            self.beginRemoveRows(QModelIndex(), self._max, self._max)
            self._rows.pop()
            self.endRemoveRows()
        self._rows.appendleft((index, size, time, level))
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self._rows.clear()
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: B008
        return 0 if parent.isValid() else len(COLUMNS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role == Qt.ItemDataRole.DisplayRole and orientation is Qt.Orientation.Horizontal:
            return COLUMNS[section].upper()
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        frame, size, time, level = self._rows[index.row()]
        if role == LEVEL_ROLE:
            return level
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                f"#{frame + 1}",
                f"{size:,} B",
                f"{int(time // 60):02d}:{time % 60:05.2f}",
                "",
            )[index.column()]
        return None
