import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from studio.main import build_window
from studio.models import Target
from studio.theme import DARK, LIGHT, get_theme
from studio.widgets.channel_strip import channel_gains
from studio.widgets.transport import split_time

from audiowave import AudioClip, Loop
from audiowave.audio import PlayerState

# -- pure helpers ---------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("mutes", "solos", "gains"),
    [
        ([False, False], [False, False], [1, 1]),
        ([True, False], [False, False], [0, 1]),
        ([False, False], [False, True], [0, 1]),
        ([True, True], [True, False], [1, 0]),
    ],
)
def test_solo_beats_mute(mutes, solos, gains):
    assert channel_gains(mutes, solos) == gains


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, ("00:00", ".000")),
        (3.2, ("00:03", ".200")),
        (61.9994, ("01:01", ".999")),
        (61.9996, ("01:02", ".000")),
        (3725.5, ("1:02:05", ".500")),
        (-1, ("00:00", ".000")),
    ],
)
def test_split_time(seconds, expected):
    assert split_time(seconds) == expected


# -- the assembled app ----------------------------------------------------------------------------


def test_starts_on_the_player_with_the_demo_take(window):
    assert window.stack.currentWidget() is window.player_page
    assert window._s.takes.current.name == "Demo" and window.player_page.waveform.clip is not None
    assert window.player_page.strip._channels == 2 and window.inspector.isVisible()


def test_every_page_renders_without_error(window):
    for key in ("record", "player", "stream", "styles"):
        window.show_page(key)
        assert window.grab().width() == 1440
    assert not window.inspector.isVisible()  # the Style Lab is full width
    window.show_page("player")
    assert window.inspector.isVisible()


def test_tabs_and_shortcuts_navigate(window):
    QTest.mouseClick(window.tabs._buttons["stream"], Qt.MouseButton.LeftButton)
    assert window.stack.currentWidget() is window.stream_page
    window.show_page("player")
    QTest.keyClick(window, Qt.Key.Key_M)  # marker at the playhead
    assert len(window._s.markers) == 1
    QTest.keyClick(window, Qt.Key.Key_M)
    window.show_page("stream")
    QTest.keyClick(window, Qt.Key.Key_M)  # ignored off the player page
    assert len(window._s.markers) == 2


def test_theme_toggle_restyles_everything_and_keeps_the_shape(window):
    window._s.appearance.update(style="env", bar_width=7)
    window.toggle_theme()
    assert get_theme() is LIGHT
    a = window._s.appearance.appearance(0)
    assert a.palette == LIGHT.waveform and a.style == "env" and a.bar_width == 7
    assert window.player_page.waveform.theme == LIGHT.waveform
    window.toggle_theme()
    assert get_theme() is DARK


def test_changing_appearance_reaches_the_waveform_lanes_independently(window):
    m, wf = window._s.appearance, window.player_page.waveform
    m.set_target(Target.RIGHT)
    m.update(style="dots")
    assert wf.appearance(0).style == "bars" and wf.appearance(1).style == "dots"


def test_style_lab_tile_click_changes_the_style(window):
    window.show_page("styles")
    tile = window.lab_page._tiles["env"]
    QTest.mouseClick(tile, Qt.MouseButton.LeftButton, pos=QPoint(20, 20))
    assert window._s.appearance.editing.style == "env"


def test_inspector_hides_controls_the_style_does_not_use(window):
    inspector, m = window.inspector, window._s.appearance
    m.update(style="bars")
    assert inspector._gravity_section.isVisible() and inspector._bar_sliders[0].isVisible()
    m.update(style="env")
    assert inspector._gravity_section.isVisible() and not inspector._bar_sliders[0].isVisible()
    m.update(style="rms")
    assert not inspector._gravity_section.isVisible()


def test_inspector_controls_edit_the_model_and_follow_it(window):
    inspector, m = window.inspector, window._s.appearance
    inspector._bar_sliders[0]._slider.setValue(8)  # width
    assert m.editing.bar_width == inspector._bar_sliders[0].value() > 3
    m.update(radius=4)
    assert inspector._bar_sliders[2].value() == 4  # model -> widget, without echoing back
    inspector._toggles["show_grid"].setChecked(False)
    assert m.editing.show_grid is False
    inspector._toggles["auto_gain"].setChecked(False)
    assert m.auto_gain is False and window.player_page.waveform.auto_gain is False


def test_loop_marker_and_zoom_wiring(window):
    s, page = window._s, window.player_page
    s.set_loop_region(Loop(1.0, 2.0))
    assert s.loop_enabled and page.transport.loop.isChecked() and s.player.loop == Loop(1.0, 2.0)
    page.transport.loop.click()  # untoggle: the region stays, playback stops looping
    assert s.loop == Loop(1.0, 2.0) and s.player.loop is None
    s.set_loop_region(None)
    assert not s.loop_enabled

    page.transport.zoom.set_value(50)
    page.transport.zoom.valueChanged.emit(50)
    assert s.viewport.zoom_level > 2
    s.viewport.fit()
    assert page.transport.zoom.value() == pytest.approx(
        0, abs=1
    )  # slider follows wheel/overview zoom


def test_transport_drives_the_player_and_the_playhead(qtbot, window):
    s, page = window._s, window.player_page
    page.transport.play.click()
    qtbot.waitUntil(
        lambda: s.player.state is PlayerState.PLAYING and s.player.position > 0.05,
        timeout=4000,
    )
    assert page.transport.play.property("kind") == "play"
    assert page.waveform.position == pytest.approx(s.player.position, abs=0.2)
    page.transport.stop.click()
    assert s.player.state is PlayerState.STOPPED and page.waveform.position == 0


def test_solo_and_mute_reach_the_player(window):
    strip, player = window.player_page.strip, window._s.player
    strip._mutes[1].setChecked(True)
    assert player._gains == (1.0, 0.0)
    strip._solos[1].setChecked(True)
    assert player._gains == (0.0, 1.0)
    strip._mutes[1].setChecked(False)
    strip._solos[1].setChecked(False)
    assert player._gains == (1.0, 1.0)


def test_opening_files_adds_takes_and_reports_bad_ones(qtbot, window, assets, tmp_path):
    s, messages = window._s, []
    s.message.connect(lambda text, err: messages.append((text, err)))
    take = s.open_file(assets / "test_mono.wav")
    assert take is not None and s.takes.current is take and window.player_page.strip._channels == 1
    assert s.open_file(tmp_path / "missing.wav") is None
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"nope")
    assert (
        s.open_file(bad) is None
    )  # not a valid WAV: handed to the decoder, which fails asynchronously
    qtbot.waitUntil(lambda: any("Could not open bad.wav" in m for m, _ in messages), timeout=15000)
    assert [e for _, e in messages if e] and messages[-1][1] is True
    assert s.takes.current is take  # failed opens leave the session untouched


def test_saving_a_take_roundtrips(window, tmp_path):
    take = window._s.takes.current
    path = tmp_path / "out.wav"
    assert window._s.save_take(take, path) and take.path == path
    back = AudioClip.from_wav(path)
    assert back.channels == take.clip.channels and back.frames == take.clip.frames


def test_switching_takes_resets_loop_markers_and_viewport(window):
    s = window._s
    s.set_loop_region(Loop(1, 2))
    s.add_marker(1.0)
    s.viewport.zoom(4)
    s.takes.add(AudioClip(np.zeros((1, 4000), np.float32), 8000), name="Short")
    assert (
        s.loop is None
        and s.markers == []
        and s.viewport.is_full
        and s.viewport.duration == pytest.approx(0.5)
    )


def test_stream_page_switches_role_and_validates_input(window):
    page = window.stream_page
    assert (
        page.is_sender and not page.host_box.isVisibleTo(page) and page.mic_button.isVisibleTo(page)
    )
    page.role.set_current("receiver", emit=True)
    assert (
        page.host_box.isVisibleTo(page)
        and page.play_button.isVisibleTo(page)
        and not page.mic_button.isVisibleTo(page)
    )
    assert page.port.minimum() == 6000 and page.port.maximum() == 9000
    page.host.setText("")
    errors = []
    window._s.message.connect(lambda text, err: errors.append(text))
    page.main_button.click()  # connect with no host
    assert errors and not page.receiver.is_connected


def test_stream_page_end_to_end_over_loopback(qtbot, window):
    page, s = window.stream_page, window._s
    page.port.setValue(6543)
    page.main_button.click()  # start server
    qtbot.waitUntil(lambda: page.sender.is_listening, timeout=3000)
    assert "Listening" in page.status.text()

    # a second receiver, standing in for another studio, joins
    from studio.stream import StreamReceiver

    remote = StreamReceiver()
    remote.connect_to("127.0.0.1", 6543)
    qtbot.waitUntil(
        lambda: page.sender.client_count == 1 and page.send_button.isEnabled(),
        timeout=3000,
    )
    with qtbot.waitSignal(remote.streamEnded, timeout=8000):
        page.send_button.click()
    got = remote.clip()
    assert got is not None and got.frames == s.clip.frames and page.log.rowCount() > 10
    assert "F |" in page.frames_chip.text()  # the old "Frames | Size" readout
    remote.disconnect_from()
    page.main_button.click()  # stop server
    assert not page.sender.is_listening


def test_files_given_on_the_command_line_replace_the_demo(qtbot, tmp_path, assets):
    """`python -m studio song.mp3`: the file opens (MP3 asynchronously) and the demo take is not added."""
    w = build_window(
        presets_path=tmp_path / "p.json",
        settings_path=tmp_path / "s.ini",
        files=[str(assets / "test_stereo.mp3")],
    )
    qtbot.addWidget(w)
    qtbot.waitUntil(lambda: len(w._s.takes) == 1, timeout=15000)
    assert [t.name for t in w._s.takes] == [
        "test_stereo"
    ] and w._s.takes.current.path.suffix == ".mp3"
    w._s.shutdown()
