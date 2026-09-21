"""Regenerate the README/docs screenshots from the real app, offscreen and deterministically.

python scripts/screenshots.py            # writes docs/screenshots/studio-*.png
"""

import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from studio.demo import demo_clip
from studio.main import build_window
from studio.stream import StreamReceiver
from studio.theme import DARK, LIGHT

from audiowave import Loop

OUT = Path(__file__).resolve().parent.parent / "docs" / "screenshots"
SIZE = (1440, 900)


def settle(ms: int = 1500) -> None:
    """Run the event loop for a while so background analysis (loudness) can finish."""
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def main() -> int:
    QCoreApplication.setApplicationName("AudioWaveScreenshots")
    app = QApplication(sys.argv)
    tmp = Path(tempfile.mkdtemp())
    window = build_window(presets_path=tmp / "presets.json", settings_path=tmp / "settings.ini")
    window.resize(*SIZE)
    window.show()

    s = window._s
    s.takes.add(demo_clip(6.0).gain(0.3), name="Quiet mix", select=False)
    s.takes.add(demo_clip(2.0), name="Take 1", select=False)
    s.takes.set_current(next(iter(s.takes)))
    s.set_loop_region(Loop(2.0, 4.6))
    s.add_marker(1.0, "intro")
    s.add_marker(6.0, "cut")
    page = window.player_page
    s.player.seek(
        3.2
    )  # the real player drives every view's playhead, the time readout and the spectrum
    s.find_silences(threshold_db=-40, min_duration=0.15)
    settle()

    OUT.mkdir(parents=True, exist_ok=True)

    def shot(name: str, page_key: str, view: str | None = None, light: bool = False) -> None:
        window.apply_theme(LIGHT if light else DARK)
        window.show_page(page_key)
        if view:
            page.view_switch.set_current(view, emit=True)
        settle(600)
        window.grab().save(str(OUT / f"{name}.png"))
        print("wrote", OUT / f"{name}.png")

    loud = (
        float(abs(s.clip.channel(0)).argmax()) / s.clip.sample_rate
    )  # a moment with plenty going on

    shot("studio-player", "player", "waveform")
    shot("studio-spectrogram", "player", "spectrogram")
    s.player.seek(loud)
    shot("studio-spectrum", "player", "spectrum")
    shot("studio-scope", "player", "scope")
    s.player.seek(3.2)
    page.view_switch.set_current("compare", emit=True)
    page.compare.combo.setCurrentIndex(page.compare.combo.findText("Quiet mix"))
    shot("studio-compare", "player", "compare")
    page.view_switch.set_current("waveform", emit=True)
    shot("studio-record", "record")
    shot("studio-styles", "styles")
    shot("studio-player-light", "player", "waveform", light=True)

    # Stream: a real sender and a real receiver talking over loopback, so the page shows genuine frames.
    stream = window.stream_page
    stream.port.setValue(6789)
    stream.main_button.click()
    remote = StreamReceiver()
    remote.connect_to("127.0.0.1", 6789)
    while stream.sender.client_count < 1:
        settle(100)
    stream.send_button.click()
    settle(2500)
    shot("studio-stream", "stream")
    remote.disconnect_from()
    stream.main_button.click()

    # mp3: opened through the decoder like any other file.
    s.open_file(Path(__file__).resolve().parent.parent / "tests" / "assets" / "test_stereo.mp3")
    while not any(t.name == "test_stereo" for t in s.takes):
        settle(200)
    settle(1500)
    shot("studio-mp3", "player", "waveform")
    app.processEvents()
    s.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
