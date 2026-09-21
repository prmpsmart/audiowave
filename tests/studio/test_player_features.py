"""The features added on top of the first release, exercised through the assembled window."""

import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl
from PySide6.QtGui import QDropEvent
from PySide6.QtTest import QTest

from audiowave import AudioClip, Loop
from audiowave.audio import PlayerState


def tone(seconds, amp=0.25, rate=8000, freq=440) -> AudioClip:
    t = np.arange(int(seconds * rate)) / rate
    return AudioClip(np.tile(amp * np.sin(2 * np.pi * freq * t), (2, 1)), rate)


def idle(qtbot, window):
    qtbot.waitUntil(lambda: not window._s.busy, timeout=15000)


# -- edit bar -------------------------------------------------------------------------------------


def test_edit_buttons_reflect_what_is_possible(window):
    bar, s = window.player_page.edit_bar, window._s
    trim, cut = bar._needs_selection[0], bar._needs_selection[1]
    assert (
        not trim.isEnabled() and not cut.isEnabled() and not bar.undo.isEnabled()
    )  # nothing selected yet
    s.set_loop_region(Loop(1.0, 2.0))
    assert trim.isEnabled() and cut.isEnabled()
    s.set_loop_region(None)
    assert not cut.isEnabled()


def test_cutting_through_the_toolbar_and_undoing_with_the_keyboard(qtbot, window):
    s, page = window._s, window.player_page
    before = s.clip.duration
    s.set_loop_region(Loop(1.0, 3.0))
    page.edit_bar._needs_selection[1].click()  # the scissors
    idle(qtbot, window)
    assert (
        s.clip.duration == pytest.approx(before - 2.0, abs=0.02) and page.edit_bar.undo.isEnabled()
    )
    assert window._file.text().endswith("edited")
    QTest.keyClick(window, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert s.clip.duration == pytest.approx(before) and page.edit_bar.redo.isEnabled()
    QTest.keyClick(
        window,
        Qt.Key.Key_Z,
        Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier,
    )
    assert s.clip.duration == pytest.approx(before - 2.0, abs=0.02)


def test_delete_key_and_trim_shortcut_edit_the_selection(qtbot, window):
    s = window._s
    before = s.clip.duration
    s.set_loop_region(Loop(0.0, 2.0))
    QTest.keyClick(window, Qt.Key.Key_Delete)
    idle(qtbot, window)
    assert s.clip.duration == pytest.approx(before - 2.0, abs=0.02)
    s.set_loop_region(Loop(1.0, 2.0))
    QTest.keyClick(window, Qt.Key.Key_T, Qt.KeyboardModifier.ControlModifier)
    idle(qtbot, window)
    assert s.clip.duration == pytest.approx(1.0, abs=0.02)


def test_normalize_menu_actions_reach_the_session(qtbot, window):
    window.player_page.edit_bar.action.emit("normalize_loudness", -14.0)
    idle(qtbot, window)
    qtbot.waitUntil(
        # must return a real bool: pytest-qt treats a callback returning None as success
        lambda: window._s.loudness is not None and abs(window._s.loudness.integrated + 14.0) < 0.8,
        timeout=15000,
    )
    assert "LUFS" in window.player_page._lufs_chip.text()


# -- loudness readout -----------------------------------------------------------------------------


def test_loudness_chips_fill_in_and_the_momentary_reading_follows_the_playhead(qtbot, window):
    page = window.player_page
    qtbot.waitUntil(lambda: "LUFS" in page._lufs_chip.text(), timeout=15000)
    assert page._lra_chip.text().startswith("LRA")
    window._s.player.seek(4.0)
    assert page._momentary_chip.text().startswith("M ")
    window._s.player.seek(0.1)
    assert page._momentary_chip.text() == "M −∞"  # before the first complete 400 ms window


# -- views ----------------------------------------------------------------------------------------


def test_spectrum_view_follows_the_playhead(qtbot, window):
    page = window._s and window.player_page
    window._s.takes.add(tone(4.0, freq=1000))
    page.view_switch.set_current("spectrum", emit=True)
    assert page.stack.currentWidget() is page.spectrum and not page.strip.isVisible()
    window._s.player.seek(2.0)
    assert page.spectrum.levels.max() > -20
    assert abs(page.spectrum.centres[int(page.spectrum.levels.argmax())] - 1000) < 150


def test_every_view_can_be_selected_and_rendered(window):
    page = window.player_page
    for key in ("spectrogram", "spectrum", "scope", "compare", "waveform"):
        page.view_switch.set_current(key, emit=True)
        assert window.grab().width() == 1440
    assert page.overview.isVisibleTo(page) and page.strip.isVisibleTo(page)


def test_detected_silences_are_highlighted_and_removable(qtbot, window):
    s, page = window._s, window.player_page
    rate = 8000
    t = tone(1.0, rate=rate).samples
    gap = np.zeros((2, rate), np.float32)
    s.takes.add(AudioClip(np.concatenate([t, gap, t], axis=1), rate))
    page.edit_bar.action.emit("find_silences", None)
    qtbot.waitUntil(lambda: len(page.waveform.highlights) == 1, timeout=5000)
    assert page.waveform.highlights[0].start == pytest.approx(1.0, abs=0.05)
    page.edit_bar.action.emit("remove_silences", None)
    idle(qtbot, window)
    assert s.clip.duration == pytest.approx(2.0, abs=0.03) and page.waveform.highlights == []


# -- compare --------------------------------------------------------------------------------------


def test_compare_lines_up_two_takes_and_switches_what_you_hear(qtbot, window):
    s, page = window._s, window.player_page
    quiet = s.takes.add(tone(3.0, amp=0.05), name="Quiet")
    s.takes.add(tone(5.0, amp=0.4), name="Loud")  # current = Loud (A)
    page.view_switch.set_current("compare", emit=True)
    cmp = page.compare
    assert cmp.other is quiet or cmp.other.name in ("Quiet", "Demo")
    cmp.combo.setCurrentIndex(cmp.combo.findText("Quiet"))
    assert cmp.other is quiet
    assert s.viewport.duration == pytest.approx(5.0)  # the longer of the two
    assert cmp.wave_a.clip.channels == 1 and cmp.wave_b.clip.channels == 1  # mono mixdown of each

    qtbot.waitUntil(lambda: "LU" in cmp.delta.text(), timeout=15000)
    assert cmp.delta.text().startswith("B is −")  # the quiet one is lower
    assert "Loud" in cmp._label_a.text() and "Quiet" in cmp._label_b.text()

    s.player.seek(1.0)
    cmp.listen.set_current("b", emit=True)
    assert s.player.duration == pytest.approx(3.0) and s.player.position == pytest.approx(
        1.0, abs=0.05
    )
    cmp.listen.set_current("a", emit=True)
    assert s.player.duration == pytest.approx(5.0)

    cmp.listen.set_current("b", emit=True)
    page.view_switch.set_current(
        "waveform", emit=True
    )  # leaving compare restores A and the full timeline
    assert s.player.duration == pytest.approx(5.0) and s.viewport.duration == pytest.approx(5.0)


def test_compare_with_a_single_take_offers_only_a(window):
    page = window.player_page
    page.view_switch.set_current("compare", emit=True)
    assert page.compare.other is None and page.compare.combo.count() == 0
    assert "choose a take" in page.compare._label_b.text()


def test_compare_playback_keeps_playing_across_the_switch(qtbot, window):
    s, page = window._s, window.player_page
    s.takes.add(tone(4.0), name="B")
    s.takes.add(tone(6.0), name="A")
    page.view_switch.set_current("compare", emit=True)
    s.player.play()
    qtbot.waitUntil(lambda: s.player.position > 0.1, timeout=4000)
    page.compare.listen.set_current("b", emit=True)
    assert s.player.state is PlayerState.PLAYING and s.player.duration == pytest.approx(4.0)
    s.player.stop()


# -- files ----------------------------------------------------------------------------------------


def test_dropping_an_mp3_opens_it_and_ignores_other_files(qtbot, window, assets, tmp_path):
    def drop(path):
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(path))])
        window.dropEvent(
            QDropEvent(
                QPointF(5, 5),
                Qt.DropAction.CopyAction,
                mime,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )

    count = len(window._s.takes)
    drop(assets / "test_stereo.mp3")
    qtbot.waitUntil(lambda: len(window._s.takes) == count + 1, timeout=15000)
    assert window._s.takes.current.path.suffix == ".mp3" and window._file.text().startswith(
        "test_stereo.mp3"
    )
    junk = tmp_path / "readme.txt"
    junk.write_text("x")
    drop(junk)
    qtbot.wait(100)
    assert len(window._s.takes) == count + 1


def test_the_open_menu_lists_recent_files_newest_first(qtbot, window, assets):
    window._s.open_file(assets / "test_mono.wav")
    window._s.open_file(assets / "test_stereo.wav")
    page = window.player_page
    page._fill_open_menu()
    labels = [a.text() for a in page._open_menu.actions() if a.text()]
    assert (
        labels[:3] == ["Browse…", "test_stereo.wav", "test_mono.wav"]
        and labels[-1] == "Clear recent"
    )
    page._open_menu.actions()[-1].trigger()
    page._fill_open_menu()
    assert [a.text() for a in page._open_menu.actions() if a.text()] == ["Browse…"]


# -- keyboard navigation --------------------------------------------------------------------------


def test_arrow_keys_on_the_waveform_move_the_playhead(window):
    s, wf = window._s, window.player_page.waveform
    s.player.seek(2.0)
    QTest.keyClick(wf, Qt.Key.Key_Right)
    assert s.player.position == pytest.approx(3.0, abs=0.02)
    QTest.keyClick(wf, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    assert s.player.position == pytest.approx(2.9, abs=0.02)
    QTest.keyClick(wf, Qt.Key.Key_End)
    assert s.player.position == pytest.approx(s.clip.duration, abs=0.02)
    QTest.keyClick(wf, Qt.Key.Key_Home)
    assert s.player.position == 0


# -- record page ----------------------------------------------------------------------------------


def test_record_page_shows_a_live_spectrum_of_incoming_audio(window):
    window.show_page("record")
    page = window.record_page
    rate = 44100
    t = np.arange(4096) / rate
    page._on_chunk(
        np.tile(0.5 * np.sin(2 * np.pi * 2000 * t, dtype=np.float32), (1, 1)).astype(np.float32)
    )
    assert page.spectrum.levels.max() > -20
    assert abs(page.spectrum.centres[int(page.spectrum.levels.argmax())] - 2000) < 300
    page._on_state(page._s.recorder.state)  # back to idle clears it
    assert (page.spectrum.levels <= -90).all()


def test_spectrum_shows_something_even_before_the_playhead_has_audio_behind_it(window):
    page = window.player_page
    window._s.player.seek(0.0)
    page.view_switch.set_current("spectrum", emit=True)
    assert page.spectrum.levels.max() > -60  # analyses the first window instead of showing nothing
