"""Session-level behaviour for the newer features: mp3, edits with undo, loudness, silences, recent files, tasks."""

import time

import numpy as np
import pytest
from PySide6.QtCore import QSettings
from studio.editing import EditError, apply_action
from studio.models import AppearanceModel, PresetStore, RecentFiles, TakesModel
from studio.session import Session
from studio.tasks import BackgroundTasks

from audiowave import AudioClip, Loop
from audiowave.audio import AudioPlayer, AudioRecorder


@pytest.fixture
def session(qtbot, tmp_path):
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    s = Session(
        AudioPlayer(),
        AudioRecorder(),
        AppearanceModel(),
        TakesModel(),
        PresetStore(tmp_path / "p.json"),
        RecentFiles(settings),
    )
    s.player.set_volume(0.0)
    yield s
    s.shutdown()


def tone_clip(seconds=6.0, rate=8000) -> AudioClip:
    t = np.arange(int(seconds * rate)) / rate
    return AudioClip(np.tile(0.25 * np.sin(2 * np.pi * 440 * t), (2, 1)), rate)


def wait_idle(qtbot, session):
    qtbot.waitUntil(lambda: not session.busy, timeout=15000)


# -- background tasks -----------------------------------------------------------------------------


def test_tasks_deliver_on_the_ui_thread_and_drop_superseded_results(qtbot):
    from PySide6.QtCore import QThread

    tasks, got, threads = BackgroundTasks(), [], []
    tasks.submit("k", lambda: (time.sleep(0.15), "slow")[1], lambda r: got.append(r))
    tasks.submit(
        "k", lambda: "fast", lambda r: (got.append(r), threads.append(QThread.currentThread()))
    )
    qtbot.waitUntil(lambda: bool(got), timeout=3000)
    qtbot.wait(300)
    assert (
        got == ["fast"] and threads[0] is QThread.currentThread()
    )  # the stale "slow" result never arrives
    tasks.shutdown()


def test_task_errors_reach_the_error_callback(qtbot):
    tasks, errors = BackgroundTasks(), []
    tasks.submit("boom", lambda: 1 / 0, lambda r: None, errors.append)
    qtbot.waitUntil(lambda: bool(errors), timeout=3000)
    assert "ZeroDivisionError" in errors[0]
    tasks.shutdown()


# -- opening mp3 ----------------------------------------------------------------------------------


def test_opening_an_mp3_decodes_in_the_background_into_a_take(qtbot, session, assets):
    messages = []
    session.message.connect(lambda text, err: messages.append((text, err)))
    assert session.open_file(assets / "test_stereo.mp3") is None  # asynchronous: no take yet
    qtbot.waitUntil(lambda: len(session.takes) == 1, timeout=15000)
    take = session.takes.current
    assert take.name == "test_stereo" and take.path.suffix == ".mp3" and take.clip.channels == 2
    assert (
        take.clip.duration == pytest.approx(7.1, abs=0.25)
        and session.player.duration == take.clip.duration
    )
    assert any("Decoding" in m for m, _ in messages) and not any(e for _, e in messages)
    assert [p.name for p in session.recent.paths()] == ["test_stereo.mp3"]


def test_opening_wav_is_immediate_and_bad_files_are_reported(qtbot, session, assets, tmp_path):
    take = session.open_file(assets / "test_mono.wav")
    assert take is not None and take.clip.channels == 1
    errors = []
    session.message.connect(lambda text, err: errors.append(text) if err else None)
    assert session.open_file(tmp_path / "missing.mp3") is None
    notes = tmp_path / "notes.txt"
    notes.write_text("hi")
    assert session.open_file(notes) is None
    junk = tmp_path / "junk.mp3"
    junk.write_bytes(b"not audio" * 200)
    session.open_file(junk)
    qtbot.waitUntil(lambda: len(errors) == 3, timeout=15000)
    assert (
        "not found" in errors[0].lower()
        and "not a supported" in errors[1]
        and "Could not open" in errors[2]
    )
    assert len(session.takes) == 1  # nothing was added by the failures


def test_opening_without_selecting_keeps_the_current_take(qtbot, session, assets):
    first = session.open_file(assets / "test_mono.wav")
    session.open_file(assets / "test_stereo.mp3", select=False)
    qtbot.waitUntil(lambda: len(session.takes) == 2, timeout=15000)
    assert session.takes.current is first


# -- edits with undo ------------------------------------------------------------------------------


def test_edit_undo_redo_roundtrip_through_the_session(qtbot, session):
    take = session.takes.add(tone_clip(6.0))
    original = take.clip
    session.set_loop_region(Loop(1.0, 3.0))
    session.run_edit("cut")
    wait_idle(qtbot, session)
    assert take.clip.duration == pytest.approx(4.0, abs=0.02) and take.dirty
    assert (
        session.player.duration == take.clip.duration and session.loop is None
    )  # the selection is consumed
    session.undo()
    assert take.clip is original and session.viewport.duration == 6.0
    session.redo()
    assert take.clip.duration == pytest.approx(4.0, abs=0.02)
    session.undo()
    session.undo()  # nothing left: a message, no crash
    assert take.clip is original and not take.undo


def test_edits_that_do_not_apply_explain_why(qtbot, session):
    session.takes.add(tone_clip())
    errors = []
    session.message.connect(lambda text, err: errors.append(text) if err else None)
    for action, expected in [
        ("cut", "Select a region"),
        ("remove_silences", "Find silences"),
        ("trim_silence", "no silence"),
    ]:
        session.run_edit(action)
        wait_idle(qtbot, session)
        assert expected in errors[-1], (action, errors[-1])
    assert not session.takes.current.undo  # failed edits leave no history entry


def test_history_is_bounded(qtbot, session):
    take = session.takes.add(tone_clip(2.0))
    for _ in range(15):
        session.run_edit("normalize_peak", -3.0)
        wait_idle(qtbot, session)
        session.run_edit("normalize_peak", -1.0)
        wait_idle(qtbot, session)
    assert 0 < len(take.undo) <= 10


def test_a_second_edit_while_busy_is_refused(qtbot, session):
    session.takes.add(tone_clip(60.0, 22050))
    errors = []
    session.message.connect(lambda text, err: errors.append(text) if err else None)
    session.run_edit("normalize_loudness", -20.0)  # measures loudness: takes a moment
    session.run_edit("normalize_peak")
    assert session.busy and "Still working" in errors[-1]
    wait_idle(qtbot, session)


def test_pure_edit_rules():
    clip = tone_clip(4.0)
    with pytest.raises(EditError, match="Select a region"):
        apply_action("trim", clip, None)
    with pytest.raises(EditError, match="Select a region"):
        apply_action("cut", clip, Loop(1.0, 1.0))
    out, label = apply_action("fade_in", clip)  # no selection: fades the start
    assert out.samples[0, 0] == 0 and "Fade in" in label
    out, _ = apply_action("fade_out", clip, Loop(1.0, 2.0))
    assert not out.samples[
        :, int(2.0 * 8000) + 5 :
    ].any()  # fading a selection out silences what follows it
    with pytest.raises(EditError, match="whole clip"):
        apply_action("cut", clip, Loop(0.0, 4.0))
    with pytest.raises(EditError, match="Unknown"):
        apply_action("explode", clip)


# -- loudness and silence -------------------------------------------------------------------------


def test_loudness_is_measured_in_the_background_and_cached(qtbot, session):
    with qtbot.waitSignal(
        session.loudnessChanged, timeout=15000, check_params_cb=lambda v: v is not None
    ):
        session.takes.add(tone_clip(6.0))
    # a 440 Hz sine at 0.25 amplitude in both channels: about -12 dBFS, K-weighted a touch louder or quieter
    assert session.loudness.integrated == pytest.approx(-12.0, abs=1.0)
    other = []
    session.loudness_of(session.clip, other.append)  # cached: answered synchronously
    assert other and other[0] is session.loudness


def test_normalising_loudness_changes_the_measured_loudness(qtbot, session):
    session.takes.add(tone_clip(8.0))
    session.run_edit("normalize_loudness", -20.0)
    wait_idle(qtbot, session)
    # poll the state: the re-measurement may already have finished while we waited for the edit
    qtbot.waitUntil(
        lambda: session.loudness is not None and abs(session.loudness.integrated + 20.0) < 0.5,
        timeout=15000,
    )


def test_silences_are_found_highlighted_and_removed(qtbot, session):
    rate = 8000
    tone = tone_clip(1.0, rate).samples
    gap = np.zeros((2, rate), np.float32)
    take = session.takes.add(AudioClip(np.concatenate([tone, gap, tone, gap, tone], axis=1), rate))
    with qtbot.waitSignal(
        session.silencesChanged, timeout=5000, check_params_cb=lambda v: len(v) == 2
    ):
        session.find_silences(min_duration=0.5)
    assert [(round(s.start, 1), round(s.end, 1)) for s in session.silences] == [
        (1.0, 2.0),
        (3.0, 4.0),
    ]
    session.run_edit("remove_silences")
    wait_idle(qtbot, session)
    assert (
        take.clip.duration == pytest.approx(3.0, abs=0.03) and session.silences == []
    )  # reload clears stale highlights


# -- recent files ---------------------------------------------------------------------------------


def test_recent_files_are_unique_newest_first_capped_and_prune_missing(tmp_path):
    settings = QSettings(str(tmp_path / "r.ini"), QSettings.Format.IniFormat)
    recent = RecentFiles(settings, limit=3)
    files = []
    for i in range(5):
        f = tmp_path / f"f{i}.wav"
        f.write_bytes(b"x")
        files.append(f)
        recent.add(f)
    assert [p.name for p in recent.paths()] == ["f4.wav", "f3.wav", "f2.wav"]
    recent.add(files[2])
    assert [p.name for p in recent.paths()] == ["f2.wav", "f4.wav", "f3.wav"]
    files[4].unlink()
    assert [p.name for p in recent.paths()] == ["f2.wav", "f3.wav"]
    recent.clear()
    assert recent.paths() == []
    assert [
        p.name
        for p in RecentFiles(QSettings(str(tmp_path / "r.ini"), QSettings.Format.IniFormat)).paths()
    ] == []
