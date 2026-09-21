import numpy as np

from audiowave.audio import PcmSource


def source(frames=10, channels=1) -> PcmSource:
    pcm = np.arange(frames * channels, dtype="<i2").tobytes()
    s = PcmSource(pcm, 2 * channels)
    s.open_for_playback()
    return s


def frames_of(data: bytes) -> list[int]:
    return np.frombuffer(data, "<i2").tolist()


def test_reads_sequentially_and_reports_exhaustion():
    s = source()
    assert frames_of(bytes(s.read(8))) == [0, 1, 2, 3]
    assert not s.exhausted and s.frame == 4
    assert frames_of(bytes(s.read(1000))) == [4, 5, 6, 7, 8, 9]
    assert s.exhausted and bytes(s.read(10)) == b""


def test_reads_are_frame_aligned():
    s = source(channels=2)  # 4 bytes per frame
    assert len(bytes(s.read(10))) == 8  # 10 rounds down to 2 whole frames


def test_seek_clamps():
    s = source()
    s.seek_frame(7)
    assert frames_of(bytes(s.read(100))) == [7, 8, 9]
    s.seek_frame(-5)
    assert s.frame == 0
    s.seek_frame(99)
    assert s.frame == 10


def test_loop_wraps_without_a_gap():
    s = source()
    s.set_loop(2, 5)
    s.seek_frame(3)
    got = frames_of(bytes(s.read(2 * 12)))
    assert got == [3, 4, 2, 3, 4, 2, 3, 4, 2, 3, 4, 2]
    assert not s.exhausted  # a looping source never ends


def test_starting_beyond_the_loop_plays_on_to_the_end():
    s = source()
    s.set_loop(2, 5)
    s.seek_frame(6)
    assert frames_of(bytes(s.read(100))) == [6, 7, 8, 9]


def test_clearing_and_invalid_loops():
    s = source()
    s.set_loop(2, 5)
    s.set_loop(None)
    s.seek_frame(4)
    assert frames_of(bytes(s.read(100))) == [4, 5, 6, 7, 8, 9]
    s.set_loop(5, 5)  # empty loop is ignored
    s.seek_frame(0)
    assert len(frames_of(bytes(s.read(100)))) == 10


def test_write_is_refused():
    assert source().writeData(b"x", 1) == -1
