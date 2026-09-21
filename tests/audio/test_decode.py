"""mp3 decoding. tests/assets/test_stereo.mp3 was made from test_stereo.wav with LAME at 128 kbit/s."""

import numpy as np
import pytest

from audiowave import AudioClip
from audiowave.audio import AudioDecoder, DecodeError, decode_file, is_supported, load_clip


@pytest.fixture
def original(assets) -> AudioClip:
    return AudioClip.from_wav(assets / "test_stereo.wav")


def best_alignment(
    reference: np.ndarray, decoded: np.ndarray, max_lag: int = 4000
) -> tuple[int, float]:
    """Lag (frames) at which decoded best matches reference, and the correlation there.

    MP3 adds encoder delay and padding, so the decode is a shifted, slightly longer copy.
    """
    ref = reference[:20000]

    def score(lag: int) -> float:
        seg = decoded[lag : lag + len(ref)]
        return float(np.corrcoef(ref, seg)[0, 1]) if len(seg) == len(ref) else -1.0

    coarse = max(range(0, max_lag, 16), key=score)
    best = max(
        range(max(coarse - 16, 0), coarse + 17), key=score
    )  # then refine to sample precision
    return best, score(best)


def test_decodes_an_mp3_to_a_matching_clip(qtbot, assets, original):
    clip = decode_file(assets / "test_stereo.mp3")
    assert clip.channels == 2 and clip.sample_rate == original.sample_rate
    assert abs(clip.duration - original.duration) < 0.25  # encoder padding only
    lag, correlation = best_alignment(original.channel(0), clip.channel(0))
    assert correlation > 0.98, (lag, correlation)  # same audio, lossy
    assert clip.peak() == pytest.approx(original.peak(), abs=0.15)


def test_async_decoder_reports_progress_then_the_clip(qtbot, assets):
    decoder, progress = AudioDecoder(), []
    decoder.progress.connect(progress.append)
    with qtbot.waitSignal(decoder.decoded, timeout=10000) as sig:
        decoder.decode(assets / "test_stereo.mp3")
    assert isinstance(sig.args[0], AudioClip) and progress and progress[-1] == 1.0
    assert progress == sorted(progress) and not decoder.is_running


def test_a_new_decode_cancels_the_previous_one(qtbot, assets):
    decoder, clips = AudioDecoder(), []
    decoder.decoded.connect(clips.append)
    decoder.decode(assets / "test_stereo.mp3")
    with qtbot.waitSignal(decoder.decoded, timeout=10000):
        decoder.decode(assets / "test_stereo.mp3")
    qtbot.wait(300)
    assert len(clips) == 1  # the cancelled first decode never reports


def test_errors_are_reported_not_raised_in_the_event_loop(qtbot, tmp_path):
    decoder = AudioDecoder()
    with qtbot.waitSignal(decoder.failed, timeout=3000) as sig:
        decoder.decode(tmp_path / "missing.mp3")
    assert "not found" in sig.args[0].lower()

    junk = tmp_path / "junk.mp3"
    junk.write_bytes(b"this is not audio" * 100)
    with qtbot.waitSignal(decoder.failed, timeout=10000):
        decoder.decode(junk)


def test_decode_file_raises_a_clear_error(qtbot, tmp_path):
    with pytest.raises(DecodeError):
        decode_file(tmp_path / "nope.mp3")


def test_load_clip_uses_the_right_reader(qtbot, assets):
    assert load_clip(assets / "test_mono.wav").channels == 1  # WAV: no decoder involved
    assert load_clip(assets / "test_stereo.mp3").channels == 2


def test_supported_extensions():
    assert (
        is_supported("a.MP3")
        and is_supported("b.flac")
        and is_supported("c.wav")
        and not is_supported("d.txt")
    )
