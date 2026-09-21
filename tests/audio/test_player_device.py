"""Exercises the real audio device with the volume at zero, so nothing is audible."""

import numpy as np
import pytest
from PySide6.QtMultimedia import QMediaDevices

from audiowave import AudioClip, Loop
from audiowave.audio import AudioPlayer, PlayerState, input_devices, output_devices

pytestmark = pytest.mark.skipif(
    not QMediaDevices.audioOutputs(), reason="no audio output device on this machine"
)


@pytest.fixture
def clip() -> AudioClip:
    t = np.arange(int(44100 * 0.4)) / 44100
    return AudioClip(np.stack([np.sin(2 * np.pi * 440 * t)] * 2) * 0.3, 44100)


@pytest.fixture
def player(qtbot, clip):
    p = AudioPlayer()
    p.set_volume(0.0)
    p.load(clip)
    yield p
    p.stop()


def test_device_lists_expose_a_default():
    outs = output_devices()
    assert outs and sum(d.is_default for d in outs) == 1 and all(d.name for d in outs)
    assert isinstance(input_devices(), list)


def test_play_advances_the_position_then_finishes(qtbot, player, clip):
    positions = []
    player.positionChanged.connect(positions.append)
    with qtbot.waitSignal(player.finished, timeout=4000):
        player.play()
    assert player.state is PlayerState.STOPPED and player.position == pytest.approx(
        clip.duration, abs=0.02
    )
    assert len(positions) > 3 and positions == sorted(positions)  # monotonic, from the device clock


def test_pause_freezes_the_position_and_resume_continues(qtbot, player):
    player.play()
    qtbot.waitUntil(lambda: player.position > 0.05, timeout=3000)
    player.pause()
    frozen = player.position
    qtbot.wait(120)
    assert player.state is PlayerState.PAUSED and player.position == frozen
    player.play()
    qtbot.waitUntil(lambda: player.position > frozen + 0.03, timeout=3000)


def test_seek_while_stopped_and_playing(qtbot, player):
    player.seek(0.3)
    assert player.position == pytest.approx(0.3, abs=1e-3) and player.state is PlayerState.STOPPED
    player.seek(0.05)
    player.play()
    player.seek(0.2)
    assert player.position >= 0.2 - 0.01
    player.stop()
    assert player.position == 0.0


def test_loop_keeps_playing_past_the_loop_end(qtbot, player):
    player.set_loop(Loop(0.05, 0.15))
    player.play()
    qtbot.wait(700)  # longer than the clip: without the loop it would already have finished
    assert player.state is PlayerState.PLAYING and 0.05 - 0.02 <= player.position <= 0.15 + 0.02
    player.set_loop(None)
    with qtbot.waitSignal(player.finished, timeout=4000):
        pass


def test_speed_and_volume_are_clamped_and_stored(player):
    player.set_speed(50)
    assert player.speed == 4.0
    player.set_speed(0.01)
    assert player.speed == 0.25
    player.set_volume(3)
    assert player.volume == 1.0
    player.set_volume(0)


def test_faster_speed_finishes_sooner(qtbot, player):
    player.set_speed(2.0)
    import time

    t0 = time.monotonic()
    with qtbot.waitSignal(player.finished, timeout=4000):
        player.play()
    assert time.monotonic() - t0 < 0.4 * 0.9


def test_playing_with_no_clip_is_a_noop(qtbot):
    p = AudioPlayer()
    p.play()
    assert p.state is PlayerState.STOPPED and p.position == 0.0


def test_channel_gains_can_be_set_and_cleared(player):
    player.set_channel_gains([1.0, 0.0])
    assert player._gains == (1.0, 0.0)
    left = np.frombuffer(player._pcm, "<i2").reshape(-1, 2)
    assert (
        np.abs(left[:, 0]).max() > 0 and not left[:, 1].any()
    )  # right channel muted in the encoded stream
    player.set_channel_gains(None)
    assert np.frombuffer(player._pcm, "<i2").reshape(-1, 2)[:, 1].any()
