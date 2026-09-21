import pytest

from audiowave.widgets import Viewport
from audiowave.widgets.ruler import format_time, nice_step, ticks


def vp(duration=100.0) -> Viewport:
    v = Viewport()
    v.set_duration(duration)
    return v


def test_starts_fully_zoomed_out():
    v = vp()
    assert (v.start, v.end, v.is_full, v.zoom_level) == (0, 100, True, 1.0)


def test_zoom_keeps_the_anchor_under_the_cursor():
    v = vp()
    before = v.fraction(30.0)
    v.zoom(4, anchor=30.0)
    assert v.span == pytest.approx(25.0) and v.fraction(30.0) == pytest.approx(before)


def test_range_is_clamped_to_the_clip():
    v = vp()
    v.set_range(-50, 20)
    assert (v.start, v.end) == (0, 70) or v.span == pytest.approx(70) and v.start >= 0
    v.set_range(90, 200)
    assert v.end == pytest.approx(100) and v.start >= 0
    v.zoom(1e9)
    assert v.span == pytest.approx(Viewport.MIN_SPAN)
    v.zoom(1e-9)
    assert v.is_full


def test_pan_and_fit_and_signal(qtbot):
    v = vp()
    v.set_range(10, 30)
    with qtbot.waitSignal(v.changed, timeout=500):
        v.pan(5)
    assert (v.start, v.end) == (15, 35)
    v.pan(1000)
    assert v.end == pytest.approx(100) and v.span == pytest.approx(20)
    v.fit()
    assert v.is_full


def test_unchanged_range_does_not_emit(qtbot):
    v = vp()
    with qtbot.assertNotEmitted(v.changed):
        v.set_range(0, 100)


def test_ensure_visible_scrolls_but_never_zooms():
    v = vp()
    v.set_range(0, 10)
    v.ensure_visible(50)
    assert v.span == pytest.approx(10) and v.start <= 50 <= v.end
    v.set_range(20, 30)
    start = v.start
    v.ensure_visible(25)
    assert v.start == start  # already visible: untouched


def test_nice_step_never_crowds_labels():
    for span in (0.05, 3, 47, 600, 7200):
        step = nice_step(span, 1000, 80)
        assert step / span * 1000 >= 80 - 1e-6


def test_ticks_mark_majors_on_multiples_of_the_step():
    result = ticks(0, 10, 5)
    majors = [t for t, m in result if m]
    assert majors == [0.0, 5.0, 10.0] and len(result) > len(majors)


@pytest.mark.parametrize(
    ("t", "step", "text"),
    [(0, 1, "0:00"), (65, 1, "1:05"), (3.5, 0.5, "0:03.5"), (3.25, 0.05, "0:03.25"), (3725, 1, "1:02:05"), (-4, 1, "0:00")],
)
def test_format_time(t, step, text):
    assert format_time(t, step) == text
