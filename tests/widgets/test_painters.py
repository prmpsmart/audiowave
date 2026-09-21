import numpy as np
import pytest
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath

from audiowave import Appearance, Gravity
from audiowave.core import Peaks
from audiowave.widgets import (
    PaintJob,
    WavePainter,
    get_painter,
    painter_names,
    register,
)
from audiowave.widgets.lane import LaneRenderer

W, H = 240, 90


def make_peaks(n: int) -> Peaks:
    t = np.linspace(0, 6 * np.pi, n)
    amp = np.abs(np.sin(t)) * 0.8 + 0.05
    return Peaks(
        (-amp).astype(np.float32),
        amp.astype(np.float32),
        (amp * 0.6).astype(np.float32),
    )


def render(style: str, appearance: Appearance | None = None) -> QImage:
    a = (appearance or Appearance()).with_(style=style)
    painter = get_painter(style)
    resolved = painter.resolve(a)
    image = QImage(W, H, QImage.Format.Format_ARGB32)
    image.fill(QColor("#000000"))
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    n = painter.buckets(W, resolved)
    painter.paint(p, PaintJob(QRectF(0, 0, W, H), make_peaks(n), resolved), QColor("#ffffff"))
    p.end()
    return image


def lit_pixels(image: QImage) -> int:
    ptr = image.constBits()
    arr = np.frombuffer(ptr, np.uint8).reshape(image.height(), image.bytesPerLine() // 4, 4)[
        :, : image.width()
    ]
    return int((arr[..., :3].max(axis=2) > 40).sum())


def test_every_registered_style_draws_something_inside_its_rect():
    names = painter_names()
    assert {
        "bars",
        "capsule",
        "hair",
        "env",
        "line",
        "stairs",
        "dots",
        "rms",
        "ground",
        "radial",
    } <= set(names)
    for name in names:
        image = render(name)
        assert 200 < lit_pixels(image) < W * H * 0.9, name


def test_styles_look_different_from_each_other():
    sums = {name: render(name).constBits().tobytes() for name in ("bars", "env", "dots", "line")}
    assert len(set(sums.values())) == 4


@pytest.mark.parametrize("gravity", list(Gravity))
def test_gravity_changes_which_half_is_drawn(gravity):
    image = render("bars", Appearance(gravity=gravity, show_midline=False))
    top = lit_pixels(image.copy(0, 0, W, H // 2 - 2))
    bottom = lit_pixels(image.copy(0, H // 2 + 2, W, H // 2 - 2))
    if gravity is Gravity.MAX:
        assert top > 0 and bottom == 0
    elif gravity is Gravity.MIN:
        assert bottom > 0 and top == 0
    else:
        assert top > 0 and bottom > 0


def test_capsule_and_hairline_resolve_their_forced_settings():
    base = Appearance(bar_width=6, radius=0)
    assert get_painter("capsule").resolve(base).radius == 3
    hair = get_painter("hair").resolve(base)
    assert hair.bar_width == 1 and hair.radius == 0


def test_unknown_style_falls_back_to_bars():
    assert get_painter("does-not-exist").name == "bars"


def test_a_new_style_is_just_a_registered_class():
    @register
    class Flat(WavePainter):
        name = "test-flat"
        label = "Flat"

        def paint(self, painter, job, color):
            painter.fillRect(job.rect, color)

    assert "test-flat" in painter_names()
    assert lit_pixels(render("test-flat")) == W * H
    with pytest.raises(ValueError):
        register(Flat)  # names are unique


def test_radial_played_region_is_a_clockwise_pie():
    radial = get_painter("radial")
    rect = QRectF(0, 0, 100, 100)
    half = radial.played_region(rect, 0.5)
    assert isinstance(half, QPainterPath)
    assert half.contains(rect.center() + rect.center() * 0.5) and not half.contains(
        rect.center() * 0.5
    )  # right yes, left no
    assert radial.played_region(rect, 1.0) == rect


def test_default_played_region_is_the_left_fraction():
    region = get_painter("bars").played_region(QRectF(10, 0, 200, 50), 0.25)
    assert region == QRectF(10, 0, 50, 50)


def test_lane_renderer_colours_played_and_unplayed_and_caches(qapp):
    a = Appearance(style="env", show_midline=False).with_palette(
        played="#ff0000", unplayed="#0000ff"
    )
    style = get_painter("env")
    peaks = make_peaks(style.buckets(W, a))
    lane, image = LaneRenderer(), QImage(W, H, QImage.Format.Format_ARGB32)
    image.fill(QColor("#000000"))
    p = QPainter(image)
    lane.paint(p, QRectF(0, 0, W, H), peaks, a, 0.5, token="t")
    first_key = lane._key
    lane.paint(p, QRectF(0, 0, W, H), peaks, a, 0.7, token="t")  # only the playhead moved
    assert lane._key == first_key
    p.end()
    left, right = QColor(image.pixel(W // 4, H // 2)), QColor(image.pixel(3 * W // 4, H // 2))
    assert (
        left.red() > 150 > left.blue() or right.blue() > 150
    )  # mid-lane pixels use the two colours
