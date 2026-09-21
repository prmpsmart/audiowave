"""Application entry point and composition root: the one place where concrete objects are wired together."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from audiowave import Appearance
from audiowave.audio import AudioPlayer, AudioRecorder, is_supported
from studio.demo import demo_clip
from studio.main_window import MainWindow
from studio.models import AppearanceModel, PresetStore, RecentFiles, TakesModel
from studio.session import Session
from studio.theme import DARK, Theme, load_fonts, set_theme


def default_presets_path() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppConfigLocation)
    return Path(base) / "presets.json"


def build_window(
    theme: Theme = DARK,
    presets_path: Path | None = None,
    settings_path: Path | None = None,
    demo: bool = True,
    files: list[str] | None = None,
) -> MainWindow:
    """Create the window with all its services. Requires a QApplication to exist."""
    fonts = load_fonts()
    set_theme(theme)
    QApplication.instance().setFont(QFont(fonts.sans, 10))  # type: ignore[union-attr]

    appearance = AppearanceModel(Appearance(palette=theme.waveform))
    takes = TakesModel()
    settings = (
        QSettings(str(settings_path), QSettings.Format.IniFormat) if settings_path else QSettings()
    )
    session = Session(
        AudioPlayer(),
        AudioRecorder(),
        appearance,
        takes,
        PresetStore(presets_path or default_presets_path()),
        RecentFiles(settings),
    )
    window = MainWindow(session, fonts, theme)
    session.setParent(window)

    for path in files or []:
        session.open_file(path)  # WAV opens at once; MP3 and friends decode in the background
    if not files and demo:
        takes.add(demo_clip(), name="Demo")  # only when nothing was asked for
    return window


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    QCoreApplication.setOrganizationName("PRMPSmart")
    QCoreApplication.setApplicationName("AudioWave")
    app = QApplication(argv)
    window = build_window(files=[a for a in argv[1:] if is_supported(a)])
    window.show()
    return app.exec()
