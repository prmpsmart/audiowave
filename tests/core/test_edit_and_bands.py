import numpy as np
import pytest

from audiowave import AudioClip
from audiowave.core import band_levels, edit, measure_loudness


def ramp(seconds=2.0, rate=1000, channels=1) -> AudioClip:
    """Sample value equals its frame index / total: easy to check where samples went."""
    n = int(seconds * rate)
    return AudioClip(np.tile(np.arange(n, dtype=np.float32) / n, (channels, 1)), rate)


# -- keep / cut / remove_ranges ---------------------------------------------------------------------


def test_keep_trims_to_the_range():
    out = edit.keep(ramp(), 0.5, 1.5)
    assert out.frames == 1000 and out.samples[0, 0] == pytest.approx(0.25, abs=1e-3)
    with pytest.raises(ValueError):
        edit.keep(ramp(), 1.0, 1.0)


def test_cut_removes_the_middle_exactly_without_a_crossfade():
    clip = ramp()
    out = edit.cut(clip, 0.5, 1.0, crossfade=0)
    assert out.frames == 1500
    assert np.array_equal(out.samples[0, :500], clip.samples[0, :500])
    assert np.array_equal(out.samples[0, 500:], clip.samples[0, 1000:])


def test_a_crossfade_blends_the_join_and_shortens_by_its_length():
    clip = AudioClip(np.concatenate([np.ones((1, 1000)), -np.ones((1, 1000))], axis=1), 1000)
    out = edit.cut(
        clip, 0.9, 1.1, crossfade=0.02
    )  # keeps 900 of +1 and 900 of -1, joined over 20 frames
    assert out.frames == 1800 - 20
    join = out.samples[0, 880:900]
    assert (
        join[0] > 0.9 and join[-1] < -0.9 and (np.diff(join) < 0).all()
    )  # smooth monotonic hand-over


def test_remove_ranges_merges_overlaps_and_handles_edges():
    out = edit.remove_ranges(ramp(), [(1.5, 2.0), (0.2, 0.5), (0.4, 0.6), (0.0, 0.1)], crossfade=0)
    assert out.frames == 2000 - 500 - 400 - 100 + 0  # overlap 0.4-0.5 counted once
    with pytest.raises(ValueError):
        edit.remove_ranges(ramp(), [(0, 2)])


def test_edits_never_modify_their_input():
    clip = ramp()
    before = clip.samples.copy()
    edit.cut(clip, 0.2, 0.4)
    edit.fade_in(clip, 0.5)
    edit.silence_range(clip, 0.0, 1.0)
    edit.normalize_peak(clip)
    assert np.array_equal(clip.samples, before)


# -- fades / gain -----------------------------------------------------------------------------------


@pytest.mark.parametrize("curve", ["linear", "cosine"])
def test_fades_ramp_from_and_to_silence(curve):
    ones = AudioClip(np.ones((2, 1000), np.float32), 1000)
    fi = edit.fade_in(ones, 0.5, curve)
    assert (
        fi.samples[0, 0] == 0
        and fi.samples[0, 499] == pytest.approx(1, abs=0.01)
        and fi.samples[0, 900] == 1
    )
    assert (np.diff(fi.samples[0, :500]) >= 0).all()
    fo = edit.fade_out(ones, 0.5, curve)
    assert (
        fo.samples[0, -1] == 0
        and fo.samples[0, 100] == 1
        and (np.diff(fo.samples[0, 500:]) <= 0).all()
    )


def test_fade_over_a_selection_silences_beyond_it():
    ones = AudioClip(np.ones((1, 1000), np.float32), 1000)
    out = edit.fade(ones, 0.4, 0.6, "in", "linear")
    assert (
        not out.samples[0, :400].any()
        and out.samples[0, 599] == pytest.approx(1, abs=0.01)
        and out.samples[0, 800] == 1
    )


def test_silence_range_and_gain_and_peak_normalise():
    ones = AudioClip(np.full((1, 1000), 0.5, np.float32), 1000)
    out = edit.silence_range(ones, 0.2, 0.4)
    assert out.frames == 1000 and not out.samples[0, 200:400].any() and out.samples[0, 0] == 0.5
    assert edit.gain_db(ones, -6.0206).peak() == pytest.approx(0.25, abs=1e-3)
    assert edit.normalize_peak(ones, -6.0206).peak() == pytest.approx(0.5, abs=1e-3)
    assert edit.normalize_peak(AudioClip.silence(1, 1000)).peak() == 0  # silent input is left alone


def test_normalize_loudness_hits_the_target_or_stops_at_the_ceiling():
    t = np.arange(48000 * 6) / 48000
    quiet = AudioClip(np.tile(0.02 * np.sin(2 * np.pi * 997 * t), (2, 1)), 48000)  # about -34 LUFS
    out, applied = edit.normalize_loudness(quiet, -20.0)
    assert applied == pytest.approx(14.0, abs=0.3) and measure_loudness(
        out
    ).integrated == pytest.approx(-20, abs=0.3)
    # asking for a very loud target must not clip: the gain is limited by the peak ceiling
    out, applied = edit.normalize_loudness(quiet, -3.0, ceiling_db=-1.0)
    assert out.peak() <= 10 ** (-1 / 20) + 1e-4 and applied < 31


# -- silence ----------------------------------------------------------------------------------------


def make_gappy(rate=1000) -> AudioClip:
    tone = np.full(1000, 0.5, np.float32)
    quiet = np.zeros(600, np.float32)
    return AudioClip(np.concatenate([quiet, tone, quiet, tone, quiet])[None, :], rate)


def test_silent_ranges_and_trim_silence():
    clip = make_gappy()
    ranges = edit.silent_ranges(clip, min_duration=0.3)
    assert [(round(a, 1), round(b, 1)) for a, b in ranges] == [(0.0, 0.6), (1.6, 2.2), (3.2, 3.8)]
    trimmed = edit.trim_silence(clip, padding=0.05)
    assert trimmed.duration == pytest.approx(
        3.8 - 0.6 - 0.6 + 0.1, abs=0.03
    )  # both ends trimmed, 50 ms kept on each
    loud = AudioClip(np.full((1, 500), 0.5, np.float32), 1000)
    assert edit.trim_silence(loud) is loud  # nothing to trim: same object back


def test_removing_the_detected_silences_leaves_only_the_tones():
    clip = make_gappy()
    out = edit.remove_ranges(clip, edit.silent_ranges(clip), crossfade=0)
    assert out.frames == 2000 and (out.samples == 0.5).all()


# -- spectrum bands ---------------------------------------------------------------------------------


def test_a_tone_lights_only_its_band():
    rate = 44100
    t = np.arange(4096) / rate
    centres, levels = band_levels(0.5 * np.sin(2 * np.pi * 1000 * t), rate)
    peak = int(levels.argmax())
    assert abs(centres[peak] - 1000) / 1000 < 0.12 and levels[peak] == pytest.approx(-6, abs=2)
    assert (
        levels[np.abs(np.log2(centres / 1000)) > 1.5].max() < -50
    )  # everything an octave and a half away is far below
    assert len(centres) == 48 and (np.diff(centres) > 0).all()


def test_band_levels_handle_silence_and_short_input():
    _, silent = band_levels(np.zeros(100, np.float32), 44100)
    assert (silent <= -90).all()
    centres, levels = band_levels(np.ones(50, np.float32), 8000, bands=16)
    assert len(centres) == len(levels) == 16 and np.isfinite(levels).all() and centres[-1] < 4000
