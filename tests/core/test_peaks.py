from itertools import pairwise

import numpy as np
import pytest

from audiowave.core import ClipPeaks, LivePeaks, PeakPyramid, Peaks


def brute(x, start, stop, buckets):
    edges = np.linspace(start, stop, buckets + 1).astype(int)
    mn, mx, rms = [], [], []
    for a, b in pairwise(edges):
        seg = x[a : max(b, a + 1)]
        mn.append(seg.min())
        mx.append(seg.max())
        rms.append(np.sqrt(np.mean(seg**2)))
    return np.array(mn), np.array(mx), np.array(rms)


def test_direct_query_matches_brute_force():
    x = np.random.default_rng(0).uniform(-1, 1, 5000).astype(np.float32)
    p = PeakPyramid(x).query(0, 5000, 100)
    mn, mx, rms = brute(x, 0, 5000, 100)
    assert len(p) == 100
    assert (
        np.allclose(p.minimum, mn)
        and np.allclose(p.maximum, mx)
        and np.allclose(p.rms, rms, atol=1e-6)
    )


def test_pyramid_level_query_is_close_to_brute_force():
    x = np.random.default_rng(1).uniform(-1, 1, 2_000_000).astype(np.float32)
    pyr = PeakPyramid(x)
    p = pyr.query(0, len(x), 400)
    mn, mx, _ = brute(x, 0, len(x), 400)
    assert np.abs(p.maximum - mx).max() < 0.02 and np.abs(p.minimum - mn).max() < 0.02


def test_global_extremes_survive_every_zoom():
    x = np.zeros(1_000_000, np.float32)
    x[123_456] = 0.9
    x[777_777] = -0.8
    pyr = PeakPyramid(x)
    for buckets in (1, 7, 64, 900):
        p = pyr.query(0, len(x), buckets)
        assert p.maximum.max() == pytest.approx(0.9) and p.minimum.min() == pytest.approx(-0.8)


def test_zoomed_in_beyond_sample_resolution():
    x = np.arange(10, dtype=np.float32)
    p = PeakPyramid(x).query(2, 6, 40)  # more buckets than samples
    assert len(p) == 40 and set(np.unique(p.maximum)) <= {2.0, 3.0, 4.0, 5.0}


def test_out_of_range_and_empty_queries():
    pyr = PeakPyramid(np.ones(100, np.float32))
    assert len(pyr.query(-50, 500, 10)) == 10
    assert not pyr.query(50, 50, 10).maximum.any()
    assert len(pyr.query(0, 100, 0)) == 0
    assert len(PeakPyramid(np.zeros(0, np.float32)).query(0, 10, 5)) == 5


def test_clip_peaks_time_query(stereo):
    cp = ClipPeaks(stereo)
    left, right = cp.query(0.0, 2.0, 50)
    assert cp.channels == 2 and cp.duration == pytest.approx(2.0)
    assert left.maximum.max() == pytest.approx(1.0, abs=1e-3) and not right.maximum.any()
    early = cp.query(0.0, 0.5, 20)[0]
    assert early.maximum.max() < 0.0  # first quarter of the ramp is still negative


def test_peaks_helpers():
    p = Peaks(
        np.array([-1, -2], np.float32),
        np.array([3, 4], np.float32),
        np.zeros(2, np.float32),
    )
    assert list(p.amplitude) == [2.0, 3.0]
    assert len(Peaks.concatenate([p, p])) == 4 and len(Peaks.concatenate([])) == 0


def test_live_peaks_match_batch_result_for_any_chunking():
    x = np.random.default_rng(2).uniform(-1, 1, (2, 5000)).astype(np.float32)
    live = LivePeaks(2, samples_per_bucket=100)
    for a in range(0, 5000, 333):
        live.append(x[:, a : a + 333])
    got = live.peaks()
    assert live.frames == 5000 and len(got[0]) == 50
    ref = x[0].reshape(50, 100)
    assert np.allclose(got[0].maximum, ref.max(axis=1)) and np.allclose(
        got[0].minimum, ref.min(axis=1)
    )
    assert np.allclose(got[1].rms, np.sqrt((x[1].reshape(50, 100) ** 2).mean(axis=1)), atol=1e-6)


def test_live_peaks_partial_bucket_tail_and_validation():
    live = LivePeaks(1, samples_per_bucket=10)
    live.append(np.ones((1, 25), np.float32))
    assert len(live.peaks()[0]) == 3 and len(live.tail(2)[0]) == 2
    live.clear()
    assert live.frames == 0 and len(live.peaks()[0]) == 0
    with pytest.raises(ValueError):
        live.append(np.ones((2, 5), np.float32))
