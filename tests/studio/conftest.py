import pytest
from studio.main import build_window


@pytest.fixture
def window(qtbot, tmp_path):
    """The whole app, silent, with presets and settings in a temp dir."""
    w = build_window(presets_path=tmp_path / "presets.json", settings_path=tmp_path / "s.ini")
    qtbot.addWidget(w)
    w.resize(1440, 900)
    w.show()
    w._s.player.set_volume(0.0)
    yield w
    w._s.player.stop()
    w._s.shutdown()
