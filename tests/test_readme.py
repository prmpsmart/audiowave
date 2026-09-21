"""Every code block in the README that is marked ``<!-- readme-test -->`` is executed for real.

The README uses friendly file names; here they are backed by the test assets:
song.wav -> test_stereo.wav, voice.mp3 -> test_stereo.mp3. Code runs in a scratch directory (so ``out.wav``
etc. do not litter the repo), headless, silent, and any ``app.exec()`` returns after half a second.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
README = (ROOT / "README.md").read_text()
BLOCKS = re.findall(r"<!-- readme-test -->\s*```python\n(.*?)```", README, re.S)

PRELUDE = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
_exec = QApplication.exec
QApplication.exec = staticmethod(lambda *a, **k: (QTimer.singleShot(500, QApplication.instance().quit), _exec(*a, **k))[1])
from audiowave.audio import player as _player
_init = _player.AudioPlayer.__init__
def _silent_init(self, *a, **k):
    _init(self, *a, **k)
    self._volume = 0.0  # the README plays audio; the test must not
_player.AudioPlayer.__init__ = _silent_init
"""


def test_the_readme_has_runnable_examples():
    assert len(BLOCKS) >= 8, "the README should demonstrate the library with code that is tested"


@pytest.mark.parametrize("index", range(len(BLOCKS)))
def test_readme_example_runs(index, tmp_path):
    assets = ROOT / "tests" / "assets"
    shutil.copy(assets / "test_stereo.wav", tmp_path / "song.wav")
    shutil.copy(assets / "test_stereo.mp3", tmp_path / "voice.mp3")
    script = tmp_path / "example.py"
    script.write_text(PRELUDE + BLOCKS[index])
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, str(script)], cwd=tmp_path, env=env, capture_output=True, text=True, timeout=120
    )
    assert result.returncode == 0, f"README block {index} failed:\n{BLOCKS[index]}\n{result.stderr[-1500:]}"
