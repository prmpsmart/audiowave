"""The smallest useful audiowave app: open a WAV, show its waveform, click to seek, Space to play.

    python examples/waveform_player.py path/to/file.wav

Uses only the library (no studio code). Controls: click or drag to seek, drag on the ruler to loop
a region, Ctrl/Cmd + wheel to zoom, wheel to scroll, Space to play / pause.
"""

import sys

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from audiowave import Appearance, AudioClip
from audiowave.audio import AudioPlayer
from audiowave.binding import bind_player
from audiowave.widgets import OverviewView, Viewport, WaveformView


def main(path: str) -> int:
    app = QApplication(sys.argv)

    clip = AudioClip.from_wav(path)
    viewport = Viewport()  # shared, so the overview and the waveform scroll and zoom together
    waveform = WaveformView(viewport)
    overview = OverviewView(viewport)
    overview.setFixedHeight(56)

    waveform.set_appearance(Appearance(style="capsule"))
    waveform.set_auto_gain(True)  # stretch quiet recordings so they fill the lane
    waveform.set_clip(clip)
    overview.set_clip(clip, waveform.clip_peaks)  # reuse the envelope instead of computing it twice

    player = AudioPlayer()
    player.load(clip)
    bind_player(player, waveform, overview)  # position, seek, loop and follow: one call
    QShortcut(QKeySequence("Space"), waveform, activated=player.toggle)

    window = QWidget()
    window.setWindowTitle(path)
    layout = QVBoxLayout(window)
    layout.addWidget(overview)
    layout.addWidget(waveform, 1)
    window.resize(1000, 420)
    window.show()
    return app.exec()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
