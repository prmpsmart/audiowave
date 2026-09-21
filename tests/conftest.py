import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest

from audiowave.core import AudioClip

ASSETS = Path(__file__).parent / "assets"


@pytest.fixture(scope="session")
def assets() -> Path:
    return ASSETS


@pytest.fixture
def sine() -> AudioClip:
    """One second of a 440 Hz sine at half scale, 8 kHz mono."""
    t = np.arange(8000) / 8000
    return AudioClip(0.5 * np.sin(2 * np.pi * 440 * t), 8000)


@pytest.fixture
def stereo() -> AudioClip:
    """Two seconds: left is a loud ramp, right is silent."""
    n = 16000
    left = np.linspace(-1, 1, n, dtype=np.float32)
    return AudioClip(np.stack([left, np.zeros(n, np.float32)]), 8000)
