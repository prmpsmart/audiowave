import io
import struct

import numpy as np
import pytest

from audiowave.core import AudioClip, SampleFormat, WavError


@pytest.mark.parametrize("name", ["test.wav", "test_mono.wav", "test_stereo.wav"])
def test_reads_bundled_assets(assets, name):
    clip = AudioClip.from_wav(assets / name)
    assert clip.frames > 0 and clip.channels in (1, 2) and clip.duration > 0
    assert 0 < clip.peak() <= 1.0


def test_stereo_asset_is_really_stereo(assets):
    assert AudioClip.from_wav(assets / "test_stereo.wav").channels == 2
    assert AudioClip.from_wav(assets / "test_mono.wav").channels == 1


@pytest.mark.parametrize("fmt", list(SampleFormat))
def test_write_then_read_roundtrip(sine, fmt):
    buf = io.BytesIO()
    sine.to_wav(buf, fmt)
    back = AudioClip.from_wav(buf.getvalue())
    assert back.sample_rate == 8000 and back.frames == sine.frames
    assert np.abs(back.samples - sine.samples).max() < 0.02


def test_reads_extensible_header():
    pcm = np.array([1000, -1000], "<i2").tobytes()
    guid = struct.pack("<H", 1) + b"\x00\x00\x00\x00\x10\x00\x80\x00\x00\xaa\x00\x38\x9b\x71"
    fmt = (
        struct.pack("<HHIIHH", 0xFFFE, 1, 8000, 16000, 2, 16)
        + struct.pack("<HHI", 22, 16, 4)
        + guid
    )
    wav = b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt) + 8 + len(pcm)) + b"WAVE"
    wav += b"fmt " + struct.pack("<I", len(fmt)) + fmt + b"data" + struct.pack("<I", len(pcm)) + pcm
    clip = AudioClip.from_wav(wav)
    assert clip.frames == 2 and clip.samples[0, 0] == pytest.approx(1000 / 32768)


def test_streamed_data_size_is_clamped():
    pcm = np.array([0, 100, 200], "<i2").tobytes()
    fmt = struct.pack("<IHHIIHH", 16, 1, 1, 8000, 16000, 2, 16)
    wav = b"RIFF\xff\xff\xff\xffWAVEfmt " + fmt + b"data" + struct.pack("<I", 0xFFFFFFFF) + pcm
    assert AudioClip.from_wav(wav).frames == 3


@pytest.mark.parametrize("junk", [b"", b"not a wav file at all", b"RIFF\x00\x00\x00\x00WAVE"])
def test_rejects_garbage(junk):
    with pytest.raises(WavError):
        AudioClip.from_wav(junk)


def test_clip_is_immutable_and_validates(sine):
    with pytest.raises(ValueError):
        sine.samples[0, 0] = 1.0
    with pytest.raises(ValueError):
        AudioClip(np.zeros((0, 5)), 8000)
    with pytest.raises(ValueError):
        AudioClip(np.zeros(5), 0)


def test_slice_mono_gain_concat(stereo):
    part = stereo.slice(0.5, 1.0)
    assert part.frames == 4000 and part.channels == 2
    assert stereo.to_mono().channels == 1
    assert stereo.gain(0.5).peak() == pytest.approx(0.5, abs=1e-3)
    joined = AudioClip.concatenate([part, part])
    assert joined.frames == 8000
    with pytest.raises(ValueError):
        AudioClip.concatenate([part, AudioClip.silence(1, 44100, 2)])
    assert stereo.slice(5, 9).frames == 0


def test_channel_peaks_and_rms(stereo, sine):
    assert stereo.channel_peaks() == pytest.approx([1.0, 0.0], abs=1e-3)
    assert sine.rms() == pytest.approx(0.5 / np.sqrt(2), rel=1e-2)
