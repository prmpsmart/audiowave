"""Regenerate the README/docs screenshots from the real app, offscreen and deterministically.

python scripts/screenshots.py            # writes docs/screenshots/studio-*.png
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication
from studio.demo import demo_clip
from studio.main import build_window
from studio.theme import DARK, LIGHT

from audiowave import Loop

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SIZE = (1440, 900)


def main() -> int:
    QCoreApplication.setApplicationName("AudioWaveScreenshots")
    app = QApplication(sys.argv)
    window = build_window(presets_path=Path(tempfile.mkdtemp()) / "presets.json")
    window.resize(*SIZE)
    window.show()

    s = window._s
    s.takes.add(demo_clip(4.0), name="Take 2", select=False)
    s.takes.add(demo_clip(2.0), name="Take 1", select=False)
    s.takes.set_current(next(iter(s.takes)))
    s.set_loop_region(Loop(2.0, 4.6))
    s.add_marker(1.0, "intro")
    s.add_marker(6.0, "cut")
    page = window.player_page
    for view in (page.waveform, page.overview):
        view.set_position(3.2)
    page.transport.set_time(3.2, s.clip.duration)

    shots = [
        ("studio-player", "player", False),
        ("studio-record", "record", False),
        ("studio-stream", "stream", False),
        ("studio-styles", "styles", False),
        ("studio-player-light", "player", True),
    ]
    OUT.mkdir(parents=True, exist_ok=True)
    for name, page_key, light in shots:
        window.apply_theme(LIGHT if light else DARK)
        window.show_page(page_key)
        app.processEvents()
        window.grab().save(str(OUT / f"{name}.png"))
        print("wrote", OUT / f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
