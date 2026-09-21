import dataclasses

import pytest

from audiowave import Appearance, Gravity, Palette


def test_defaults_are_hashable_and_immutable():
    a = Appearance()
    assert hash(a) == hash(Appearance())
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.style = "env"  # type: ignore[misc]


def test_with_returns_a_new_value():
    a = Appearance()
    b = a.with_(style="env", bar_width=5).with_palette(played="#ff0000")
    assert (a.style, a.bar_width) == ("bars", 3.0) and a.palette.played != "#ff0000"
    assert (b.style, b.bar_width, b.palette.played) == ("env", 5, "#ff0000")


def test_dict_roundtrip_including_enum_and_palette():
    a = Appearance(style="dots", gravity=Gravity.MAX, palette=Palette(played="#123456"))
    data = a.to_dict()
    assert data["gravity"] == "max" and data["palette"]["played"] == "#123456"
    assert Appearance.from_dict(data) == a


def test_from_dict_ignores_unknown_keys_and_tolerates_partial_presets():
    b = Appearance.from_dict(
        {"style": "line", "future_option": 1, "palette": {"played": "#000000", "nope": "x"}}
    )
    assert b.style == "line" and b.palette.played == "#000000" and b.bar_width == 3.0
