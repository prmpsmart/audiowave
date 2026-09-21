import numpy as np
import pytest
from PySide6.QtNetwork import QHostAddress
from studio.stream import (
    FrameDecoder,
    FrameLogModel,
    MessageType,
    ProtocolError,
    StreamReceiver,
    StreamSender,
    valid_port,
)
from studio.stream.protocol import (
    encode_end,
    encode_frame,
    encode_hello,
    parse_hello,
    split_pcm,
)

from audiowave import AudioClip, AudioFormat, SampleFormat


def local() -> QHostAddress:
    return QHostAddress(QHostAddress.SpecialAddress.LocalHost)


# -- protocol -------------------------------------------------------------------------------------


def test_messages_survive_any_chunking_of_the_byte_stream():
    stream = (
        encode_hello(44100, 2)
        + encode_frame(b"\x01\x02" * 50)
        + encode_frame(b"\xff" * 10)
        + encode_end()
    )
    for step in (1, 3, 7, 64, len(stream)):
        dec, got = FrameDecoder(), []
        for i in range(0, len(stream), step):
            got += dec.feed(stream[i : i + step])
        assert [m.type for m in got] == [
            MessageType.HELLO,
            MessageType.FRAME,
            MessageType.FRAME,
            MessageType.END,
        ]
        assert got[1].payload == b"\x01\x02" * 50


def test_audio_containing_the_old_delimiter_is_no_longer_a_problem():
    payload = b"abc<<>>def" * 5  # the legacy framing would have split this frame apart
    got = FrameDecoder().feed(encode_frame(payload))
    assert len(got) == 1 and got[0].payload == payload


def test_decoder_rejects_garbage():
    with pytest.raises(ProtocolError):
        FrameDecoder().feed(bytes([99]) + (5).to_bytes(4, "little") + b"12345")
    with pytest.raises(ProtocolError):
        FrameDecoder().feed(bytes([2]) + (1 << 30).to_bytes(4, "little"))


def test_hello_roundtrip_and_validation():
    fmt = parse_hello(FrameDecoder().feed(encode_hello(48000, 2))[0].payload)
    assert fmt == AudioFormat(48000, 2, SampleFormat.S16)
    for bad in (
        b"not json",
        b'{"rate": 1}',
        b'{"rate": 8000, "channels": 1, "format": "f32"}',
    ):
        with pytest.raises(ProtocolError):
            parse_hello(bad)


def test_split_pcm_keeps_whole_sample_frames():
    fmt = AudioFormat(1000, 2, SampleFormat.S16)  # 20 ms = 20 frames = 80 bytes
    parts = split_pcm(bytes(range(256)) * 2 + b"\x00", fmt)  # trailing odd byte is dropped
    assert all(len(p) % fmt.bytes_per_frame == 0 for p in parts) and len(parts[0]) == 80
    assert sum(map(len, parts)) == 512


def test_port_range_matches_the_old_app():
    assert valid_port(6000) and valid_port(9000) and not valid_port(5999) and not valid_port(9001)


# -- log model ------------------------------------------------------------------------------------


def test_log_model_is_newest_first_and_capped(qtbot):
    m = FrameLogModel(max_rows=3)
    for i in range(5):
        m.add(i, 1920, i * 0.02, 0.5)
    assert m.rowCount() == 3
    assert m.index(0, 0).data() == "#5" and m.index(2, 0).data() == "#3"
    assert m.index(0, 1).data() == "1,920 B"
    m.clear()
    assert m.rowCount() == 0


# -- sender <-> receiver over a real socket -------------------------------------------------------


@pytest.fixture
def link(qtbot):
    sender, receiver = StreamSender(), StreamReceiver()
    assert sender.listen(0, local())
    with qtbot.waitSignal(receiver.connectedChanged, timeout=3000):
        receiver.connect_to("127.0.0.1", sender.port)
    qtbot.waitUntil(lambda: sender.client_count == 1, timeout=3000)
    yield sender, receiver
    receiver.disconnect_from()
    sender.stop()


def test_a_clip_arrives_intact(qtbot, link):
    sender, receiver = link
    n = 8000 * 2
    clip = AudioClip(
        np.stack([np.sin(np.linspace(0, 400, n)), np.cos(np.linspace(0, 300, n))]) * 0.5,
        8000,
    )
    with qtbot.waitSignal(receiver.streamEnded, timeout=5000):
        sender.send_clip(clip)
    got = receiver.clip()
    assert (
        got is not None
        and got.channels == 2
        and got.sample_rate == 8000
        and got.frames == clip.frames
    )
    assert np.abs(got.samples - clip.samples).max() < 1e-3  # only 16-bit quantisation differs
    assert receiver.frame_count == 100 and receiver.byte_count == clip.frames * 2 * 2


def test_live_samples_stream_and_late_joiners_get_the_header(qtbot, link):
    sender, receiver = link
    frames = []
    receiver.frameReceived.connect(lambda i, size, s: frames.append(s.shape))
    sender.begin_stream(8000, 1)
    sender.send_samples(np.full((1, 800), 0.25, np.float32))  # 100 ms = 5 frames of 20 ms
    qtbot.waitUntil(lambda: len(frames) == 5, timeout=3000)
    assert receiver.format == AudioFormat(8000, 1, SampleFormat.S16)

    late = StreamReceiver()
    got_format = []
    late.formatReceived.connect(got_format.append)
    late.connect_to("127.0.0.1", sender.port)
    qtbot.waitUntil(lambda: bool(got_format), timeout=3000)  # HELLO is replayed to new clients
    late.disconnect_from()


def test_client_count_and_stop(qtbot):
    sender, receiver = StreamSender(), StreamReceiver()
    sender.listen(0, local())
    counts = []
    sender.clientsChanged.connect(counts.append)
    receiver.connect_to("127.0.0.1", sender.port)
    qtbot.waitUntil(lambda: sender.client_count == 1, timeout=3000)
    with qtbot.waitSignal(receiver.connectedChanged, timeout=3000):
        sender.stop()
    assert not sender.is_listening and counts[-1] == 0


def test_connecting_to_nothing_reports_an_error(qtbot):
    receiver = StreamReceiver()
    with qtbot.waitSignal(receiver.errorOccurred, timeout=4000) as sig:
        receiver.connect_to("127.0.0.1", 1)  # nothing listens on port 1
    assert sig.args[0]


def test_sending_without_begin_or_clients_is_harmless(qtbot):
    sender = StreamSender()
    sender.send_samples(np.zeros((1, 100), np.float32))
    sender.end_stream()
    assert sender.client_count == 0
