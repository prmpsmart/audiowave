"""The examples are documentation that must keep working, so they are executed for real."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

RUNNER = """
import sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

sys.path.insert(0, {examples!r})
original_exec = QApplication.exec
QApplication.exec = staticmethod(
    lambda *a, **k: (QTimer.singleShot(600, QApplication.instance().quit), original_exec(*a, **k))[1]
)
import {module} as example
sys.exit(example.main({args}))
"""


@pytest.mark.parametrize(
    ("module", "args"),
    [
        ("custom_style", ""),
        ("waveform_player", repr(str(ROOT / "tests" / "assets" / "test_stereo.wav"))),
    ],
)
def test_example_runs_and_exits_cleanly(module, args):
    code = RUNNER.format(examples=str(ROOT / "examples"), module=module, args=args)
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr[-800:]
    assert "Traceback" not in result.stderr
