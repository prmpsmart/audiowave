import numpy as np
import pytest

from audiowave.core import AudioFormat, SampleFormat, decode_pcm, encode_pcm


@pytest.mark.parametrize(
    ("fmt", "tolerance"),
    [
        (SampleFormat.U8, 1 / 128),
        (SampleFormat.S16, 1e-4),
        (SampleFormat.S24, 1e-6),
        (SampleFormat.S32, 1e-8),
        (SampleFormat.F32, 0),
    ],
)
def test_roundtrip_every_format(fmt, tolerance):
    rng = np.random.default_rng(1)
    samples = rng.uniform(-0.99, 0.99, (2, 500)).astype(np.float32)
    decoded = decode_pcm(encode_pcm(samples, fmt), fmt, 2)
    assert decoded.shape == (2, 500)
    assert np.abs(decoded - samples).max() <= tolerance + 1e-7


def test_channels_are_deinterleaved_not_split_in_half():
    stereo = np.array([[0.5, 0.5, 0.5], [-0.5, -0.5, -0.5]], np.float32)
    out = decode_pcm(encode_pcm(stereo, SampleFormat.S16), SampleFormat.S16, 2)
    assert out[0].mean() > 0.49 and out[1].mean() < -0.49


def test_s24_sign_extension():
    raw = bytes([0x00, 0x00, 0x80, 0xFF, 0xFF, 0x7F])  # -8388608, +8388607
    out = decode_pcm(raw, SampleFormat.S24, 1)
    assert out[0, 0] == pytest.approx(-1.0) and out[0, 1] == pytest.approx(1.0, abs=1e-6)


def test_partial_trailing_frame_is_dropped():
    assert decode_pcm(b"\x00\x01\x02", SampleFormat.S16, 1).shape == (1, 1)


def test_encode_clips_out_of_range():
    out = decode_pcm(
        encode_pcm(np.array([[2.0, -2.0]], np.float32), SampleFormat.S16), SampleFormat.S16, 1
    )
    assert out[0, 0] == pytest.approx(1.0, abs=1e-3) and out[0, 1] == pytest.approx(-1.0, abs=1e-3)


def test_format_rejects_bad_values():
    with pytest.raises(ValueError):
        AudioFormat(0, 1)
    with pytest.raises(ValueError):
        AudioFormat(44100, 0)
    assert AudioFormat(48000, 2, SampleFormat.S16).bytes_per_second == 192000
    with pytest.raises(ValueError):
        SampleFormat.from_width(5)
