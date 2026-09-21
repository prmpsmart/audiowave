import json

import pytest
from studio.models import AppearanceModel, PresetStore, TakesModel, Target

from audiowave import Appearance, AudioClip, Gravity

# -- AppearanceModel ------------------------------------------------------------------------------


def test_linked_edits_hit_both_channels_and_notify(qtbot):
    m = AppearanceModel()
    with qtbot.waitSignal(m.changed, timeout=500):
        m.update(style="env", bar_width=6)
    assert m.appearance(0) == m.appearance(1) and m.appearance(0).style == "env" and not m.mixed


def test_editing_one_channel_makes_the_model_mixed(qtbot):
    m = AppearanceModel()
    m.set_target(Target.RIGHT)
    m.update(style="dots")
    assert m.appearance(0).style == "bars" and m.appearance(1).style == "dots" and m.mixed
    assert m.editing.style == "dots"  # the inspector shows the channel being edited
    m.set_target(Target.LEFT)
    assert m.editing.style == "bars"
    m.set_target(Target.LINKED)
    m.update(radius=4)
    assert m.appearance(0).radius == m.appearance(1).radius == 4  # linked again: both move together


def test_no_op_edits_do_not_emit(qtbot):
    m = AppearanceModel()
    with qtbot.assertNotEmitted(m.changed):
        m.update(style="bars")
        m.set_target(Target.LINKED)
        m.set_auto_gain(True)


def test_palette_edit_theme_swap_and_replace_all(qtbot):
    m = AppearanceModel()
    m.update_palette(played="#123456")
    assert m.appearance(1).palette.played == "#123456"
    m.set_target(Target.LEFT)
    m.apply_palette(
        Appearance().palette.with_(played="#abcdef")
    )  # a theme change keeps the shape settings
    assert m.appearance(0).palette.played == "#abcdef" and m.target is Target.LEFT
    m.replace_all(Appearance(style="rms", gravity=Gravity.MAX))
    assert m.target is Target.LINKED and m.appearance(1).style == "rms"


# -- PresetStore ----------------------------------------------------------------------------------


def test_presets_roundtrip_delete_and_sort(tmp_path):
    store = PresetStore(tmp_path / "sub" / "presets.json")  # parent directory is created on demand
    assert store.names() == [] and store.load("nope") is None
    a = Appearance(style="dots", gravity=Gravity.MIN, bar_width=5)
    store.save("zed", a)
    store.save("alpha", Appearance())
    assert store.names() == ["alpha", "zed"] and store.load("zed") == a
    store.delete("zed")
    store.delete("never-existed")
    assert store.names() == ["alpha"]


@pytest.mark.parametrize(
    "content", ["", "not json", "[1, 2]", '{"x": 5}', '{"x": {"gravity": "sideways"}}']
)
def test_corrupt_preset_files_never_crash_and_the_store_recovers(tmp_path, content):
    path = tmp_path / "presets.json"
    path.write_text(content)
    store = PresetStore(path)
    assert (
        store.load("x") is None
    )  # unreadable, malformed or invalid entries all read as "no such preset"
    store.save("ok", Appearance())
    assert store.load("ok") == Appearance() and "ok" in json.loads(path.read_text())


# -- TakesModel -----------------------------------------------------------------------------------


def clip(seconds=0.1):
    return AudioClip.silence(seconds, 8000)


def test_takes_are_numbered_selected_and_renamed(qtbot):
    takes = TakesModel()
    with qtbot.waitSignal(takes.currentChanged, timeout=500):
        first = takes.add(clip())
    second = takes.add(clip())
    assert [t.name for t in takes] == ["Take 1", "Take 2"] and takes.current is second
    takes.rename(first, "  Intro  ")
    takes.rename(first, "   ")  # blank names are ignored
    assert first.name == "Intro"
    takes.add(clip(), select=False)
    assert takes.current is second and len(takes) == 3


def test_removing_the_current_take_selects_a_neighbour(qtbot):
    takes = TakesModel()
    a, b, c = (takes.add(clip()) for _ in range(3))
    takes.set_current(b)
    takes.remove(b)
    assert takes.current is c
    takes.remove(c)
    assert takes.current is a
    takes.remove(a)
    assert takes.current is None and len(takes) == 0
    takes.remove(a)  # removing something already gone is harmless
