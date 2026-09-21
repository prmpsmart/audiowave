"""Microphone permission (needed on macOS before the first capture)."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, QObject, Qt

try:  # Qt >= 6.5
    from PySide6.QtCore import QMicrophonePermission
except ImportError:  # pragma: no cover - older Qt has no permission API
    QMicrophonePermission = None  # type: ignore[assignment,misc]


def microphone_status() -> Qt.PermissionStatus | None:
    """Current permission state, or ``None`` if this Qt has no permission API."""
    app = QCoreApplication.instance()
    if QMicrophonePermission is None or app is None:
        return None
    return app.checkPermission(QMicrophonePermission())


def request_microphone(receiver: QObject, callback: Callable[[bool], None]) -> None:
    """Ask for microphone access if needed, then call ``callback(granted)``.

    Where the platform has no permission concept (or Qt is too old) ``callback(True)`` is called
    immediately, so callers can use one code path everywhere.
    """
    status = microphone_status()
    if status is None or status == Qt.PermissionStatus.Granted:
        callback(True)
        return
    if status == Qt.PermissionStatus.Denied:
        callback(False)
        return
    app = QCoreApplication.instance()
    app.requestPermission(  # type: ignore[union-attr]
        QMicrophonePermission(), receiver, lambda p: callback(p.status() == Qt.PermissionStatus.Granted)
    )
