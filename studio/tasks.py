"""Run pure computations off the UI thread and deliver the result back on it."""

from __future__ import annotations

import itertools
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    done = Signal(int, object)
    failed = Signal(int, str)


class _Job(QRunnable):
    def __init__(self, ident: int, fn: Callable[[], Any], signals: _Signals) -> None:
        super().__init__()
        self._ident, self._fn, self._signals = ident, fn, signals

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as error:
            self._signals.failed.emit(self._ident, f"{type(error).__name__}: {error}")
        else:
            self._signals.done.emit(self._ident, result)


class BackgroundTasks(QObject):
    """Submit ``fn`` under a ``key``; ``on_done(result)`` runs on the UI thread.

    Submitting again under the same key supersedes the earlier job: its result is dropped when it
    arrives, so a slow analysis of a clip the user has already replaced can never overwrite newer data.
    Only pass functions that read immutable data (clips are), since they run on a worker thread.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        self._signals = _Signals(
            self
        )  # lives on the UI thread, so worker emissions are queued to it
        self._signals.done.connect(self._on_done)
        self._signals.failed.connect(self._on_failed)
        self._ids = itertools.count(1)
        self._latest: dict[str, int] = {}
        self._pending: dict[int, tuple[str, Callable, Callable | None]] = {}

    def submit(
        self,
        key: str,
        fn: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        ident = next(self._ids)
        self._latest[key] = ident
        self._pending[ident] = (key, on_done, on_error)
        self._pool.start(_Job(ident, fn, self._signals))

    def is_busy(self, key: str) -> bool:
        return any(k == key and self._latest.get(k) == i for i, (k, _, _) in self._pending.items())

    def shutdown(self) -> None:
        """Wait for running jobs (call before the app exits so no worker outlives its data)."""
        self._pool.waitForDone(5000)

    def _on_done(self, ident: int, result: Any) -> None:
        key, on_done, _ = self._pending.pop(ident, (None, None, None))
        if on_done is not None and self._latest.get(key) == ident:
            on_done(result)

    def _on_failed(self, ident: int, message: str) -> None:
        key, _, on_error = self._pending.pop(ident, (None, None, None))
        if on_error is not None and self._latest.get(key) == ident:
            on_error(message)
