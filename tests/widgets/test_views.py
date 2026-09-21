import numpy as np
import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest

from audiowave import Appearance, AudioClip, LivePeaks, Loop, Marker
from audiowave.widgets import (
    LevelMeter,
    LiveWaveformView,
    OverviewView,
    SpectrogramView,
    VectorscopeView,
    WaveformView,
)


def dark_ratio(view) -> float:
    """Fraction of pixels that are NOT the flat background colour."""
    image = view.grab().toImage()
    bg = image.pixel(1, image.height() - 2)
    ptr = np.frombuffer(image.constBits(), np.uint32).reshape(image.height(), -1)[
        :, : image.width()
    ]
    return float((ptr != bg).mean())


@pytest.fixture
def view(qtbot, stereo):
    v = WaveformView()
    qtbot.addWidget(v)
    v.resize(600, 260)
    v.set_clip(stereo)
    v.show()
    return v


def test_renders_content_and_lanes(view):
    assert len(view.lane_rects()) == 2 and dark_ratio(view) > 0.05


def test_empty_view_renders_without_error(qtbot):
    v = WaveformView()
    qtbot.addWidget(v)
    v.resize(300, 120)
    assert v.grab() is not None and v.lane_rects() == []


def test_click_seeks_to_the_clicked_time(view, qtbot):
    with qtbot.waitSignal(view.seekRequested, timeout=1000) as sig:
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(300, 120))
    assert sig.args[0] == pytest.approx(view.viewport.duration / 2, abs=0.05)


def test_dragging_on_the_ruler_creates_a_loop(view, qtbot):
    with qtbot.waitSignal(view.loopChanged, timeout=1000):
        QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(150, 10))
        QTest.mouseMove(view, QPoint(300, 10))
        QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(450, 10))
    loop = view.loop
    assert loop is not None and loop.start == pytest.approx(0.5, abs=0.06) and loop.length > 0.3


def test_a_plain_click_on_the_ruler_seeks_instead_of_looping(view, qtbot):
    with qtbot.waitSignal(view.seekRequested, timeout=1000):
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(200, 10))
    assert view.loop is None


def test_loop_edges_can_be_dragged_and_double_click_clears(view, qtbot):
    view.set_loop(Loop(0.5, 1.5))
    x_end = int(view.time_to_x(1.5))
    QTest.mousePress(view, Qt.MouseButton.LeftButton, pos=QPoint(x_end, 100))
    QTest.mouseMove(view, QPoint(x_end + 60, 100))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, pos=QPoint(x_end + 60, 100))
    assert view.loop.end > 1.5 and view.loop.start == 0.5
    with qtbot.waitSignal(view.loopChanged, timeout=1000) as sig:
        QTest.mouseDClick(
            view, Qt.MouseButton.LeftButton, pos=QPoint(int(view.time_to_x(1.0)), 100)
        )
    assert sig.args == [None] and view.loop is None


def test_ctrl_wheel_zooms_plain_wheel_pans(view):
    def wheel(mods, dy=0, dx=0):
        ev = QWheelEvent(
            view.rect().center().toPointF(),
            view.mapToGlobal(view.rect().center()).toPointF(),
            QPoint(),
            QPoint(dx, dy),
            Qt.MouseButton.NoButton,
            mods,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )
        view.wheelEvent(ev)

    wheel(Qt.KeyboardModifier.ControlModifier, dy=240)
    assert view.viewport.zoom_level == pytest.approx(1.2**2, rel=0.02)
    start = view.viewport.start
    wheel(Qt.KeyboardModifier.NoModifier, dy=-120)
    assert view.viewport.start > start


def test_follow_scrolls_to_a_playhead_that_leaves_the_window(view):
    view.viewport.set_range(0, 0.5)
    view.set_follow(True)
    view.set_position(1.5)
    assert view.viewport.start <= 1.5 <= view.viewport.end
    view.set_follow(False)
    view.viewport.set_range(0, 0.5)
    view.set_position(1.9)
    assert view.viewport.end == pytest.approx(0.5)


def test_markers_are_sorted_and_clickable(view, qtbot):
    view.set_markers([Marker(1.5, "b"), Marker(0.5, "a")])
    assert [m.label for m in view.markers] == ["a", "b"]
    with qtbot.waitSignal(view.markerClicked, timeout=1000) as sig:
        QTest.mouseClick(
            view,
            Qt.MouseButton.LeftButton,
            pos=QPoint(int(view.time_to_x(0.5)) + 1, 10),
        )
    assert sig.args[0] == pytest.approx(0.5)


def test_per_channel_appearance_and_theme_follow_channel_zero(view):
    view.set_appearance(Appearance(style="env").with_palette(background="#101010"))
    view.set_appearance(Appearance(style="dots"), channel=1)
    assert view.appearance(0).style == "env" and view.appearance(1).style == "dots"
    assert view.theme.background == "#101010"
    assert dark_ratio(view) > 0.02


def test_auto_gain_makes_quiet_audio_fill_the_lane(qtbot):
    quiet = AudioClip(0.05 * np.sin(np.linspace(0, 200, 8000)), 8000)
    v = WaveformView()
    qtbot.addWidget(v)
    v.resize(400, 140)
    v.set_clip(quiet)
    plain = v._lane_peaks(0, 100).maximum.max()
    v.set_auto_gain(True)
    assert v._lane_peaks(0, 100).maximum.max() == pytest.approx(1.0, abs=1e-3) and plain < 0.1


def test_shared_viewport_syncs_overview_and_waveform(qtbot, stereo):
    wf = WaveformView()
    ov = OverviewView(wf.viewport)
    for w in (wf, ov):
        qtbot.addWidget(w)
        w.resize(500, 120)
    wf.set_clip(stereo)
    ov.set_clip(stereo, wf.clip_peaks)
    ov.show()
    wf.viewport.zoom(4, anchor=1.0)
    ov.grab()
    # click well right of the window: the shared viewport recentres there
    QTest.mouseClick(ov, Qt.MouseButton.LeftButton, pos=QPoint(450, 60))
    assert wf.viewport.start > 1.0 and dark_ratio(ov) > 0.05


def test_level_meter_rises_holds_and_falls(qtbot):
    m = LevelMeter()
    qtbot.addWidget(m)
    m.resize(10, 100)
    m.set_level(1.0)
    assert m.level_db == pytest.approx(0.0, abs=0.01)
    qtbot.wait(300)
    assert m.level_db < 0
    m.set_level(0.0)
    m.reset()
    assert m.level_db == -60.0 and m.grab() is not None


def test_live_waveform_grows_then_scrolls(qtbot):
    live = LivePeaks(1, samples_per_bucket=100)
    v = LiveWaveformView()
    qtbot.addWidget(v)
    v.resize(300, 100)
    v.set_source(live)
    empty = dark_ratio(v)
    live.append(np.random.default_rng(0).uniform(-0.8, 0.8, (1, 4000)).astype(np.float32))
    v.refresh()
    partial = dark_ratio(v)
    live.append(np.random.default_rng(1).uniform(-0.8, 0.8, (1, 400000)).astype(np.float32))
    v.refresh()
    assert partial > empty and dark_ratio(v) > partial and v.buckets_for_width() > 10


def test_spectrogram_and_vectorscope_render(qtbot, sine, stereo):
    sp = SpectrogramView()
    qtbot.addWidget(sp)
    sp.resize(500, 200)
    sp.set_clip(sine)
    assert sp.spectrogram is not None and dark_ratio(sp) > 0.05  # one tone = one bright line
    sp.viewport.zoom(4, 0.5)
    assert dark_ratio(sp) > 0.1

    vs = VectorscopeView()
    qtbot.addWidget(vs)
    vs.resize(200, 200)
    vs.set_clip(stereo)
    vs.set_position(1.0)
    assert vs.correlation() == pytest.approx(0.0, abs=1.0)  # ramp vs silence: a valid finite value
    assert dark_ratio(vs) > 0.01


# -- keyboard, highlights, spectrum ---------------------------------------------------------------


def test_keyboard_navigation_requests_seeks_and_zoom(view, qtbot):
    view.set_position(1.0)
    cases = [
        (Qt.Key.Key_Right, Qt.KeyboardModifier.NoModifier, 2.0),
        (Qt.Key.Key_Left, Qt.KeyboardModifier.NoModifier, 0.0),
        (Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier, 2.0),  # clamped to the 2 s clip
        (Qt.Key.Key_Right, Qt.KeyboardModifier.AltModifier, 1.1),
        (Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier, 0.0),
        (Qt.Key.Key_End, Qt.KeyboardModifier.NoModifier, 2.0),
    ]
    for key, mods, expected in cases:
        with qtbot.waitSignal(view.seekRequested, timeout=500) as sig:
            QTest.keyClick(view, key, mods)
        assert sig.args[0] == pytest.approx(expected), (key, mods)

    QTest.keyClick(view, Qt.Key.Key_Plus)
    assert view.viewport.zoom_level > 1.4
    QTest.keyClick(view, Qt.Key.Key_0)
    assert view.viewport.is_full
    view.viewport.set_range(0.0, 0.5)
    QTest.keyClick(view, Qt.Key.Key_PageDown)
    assert view.viewport.start == pytest.approx(0.5)


def test_highlights_are_drawn_and_do_not_intercept_the_mouse(view, qtbot):
    before = dark_ratio(view)
    view.set_highlights([Loop(0.2, 0.6), Loop(1.2, 1.5)])
    assert len(view.highlights) == 2 and dark_ratio(view) > before
    with qtbot.waitSignal(view.seekRequested, timeout=500):
        QTest.mouseClick(view, Qt.MouseButton.LeftButton, pos=QPoint(int(view.time_to_x(0.4)), 120))
    view.set_highlights([])
    assert view.highlights == []


def test_set_clip_can_leave_a_shared_viewport_alone(qtbot, sine, stereo):
    from audiowave.widgets import Viewport

    vp = Viewport()
    a, b = WaveformView(vp), WaveformView(vp)
    for w in (a, b):
        qtbot.addWidget(w)
    vp.set_duration(5.0)
    a.set_clip(sine, reset_viewport=False)
    b.set_clip(stereo, reset_viewport=False)
    assert vp.duration == 5.0 and a.clip is sine and b.clip is stereo


def test_spectrum_view_shows_the_tone_and_decays(qtbot):
    from audiowave.widgets import SpectrumView

    v = SpectrumView()
    qtbot.addWidget(v)
    v.resize(400, 160)
    rate = 44100
    t = np.arange(4096) / rate
    v.feed(0.5 * np.sin(2 * np.pi * 1000 * t), rate)
    peak_band = int(v.levels.argmax())
    assert abs(v.centres[peak_band] - 1000) / 1000 < 0.12 and v.levels.max() == pytest.approx(
        -6, abs=2.5
    )
    assert dark_ratio(v) > 0.02
    qtbot.wait(400)  # released at 45 dB/s
    assert v.levels.max() < -15
    v.clear()
    assert (v.levels <= -90).all()
    v.feed(np.zeros(0, np.float32), rate)  # empty input is ignored
