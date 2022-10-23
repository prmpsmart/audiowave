from typing import List
import enum, threading, io
from wave import Wave_read, Wave_write
from pyaudio import (
    Stream,
    PyAudio,
    paFloat32,
    paInt32,
    paInt24,
    paInt16,
    paInt8,
    paUInt8,
    paCustomFormat,
    paContinue,
    paComplete,
    paAbort,
)

__author__ = "PRMPSmart - Mimi Peach, prmpsmart"
__all__ = [
    "AudioWaveRecorder",
    "AudioWavePlayer",
    "AudioWaveFormat",
    "AudioWaveState",
    "AudioWaveError",
    "AudioWaveEvent",
    "AudioWaveFrames",
    "AudioWave",
]


class AudioWaveError(enum.Enum):
    """Enums for Errors"""

    Read = 1
    Write = 2
    Create = 3
    Stop = 4
    Close = 5


class AudioWaveFormat(enum.Enum):
    """Enums for Format corresponding with the pyAudio"""

    Float32 = paFloat32
    Int32 = paInt32
    Int24 = paInt24
    Int16 = paInt16
    Int8 = paInt8
    UInt8 = paUInt8
    CustomFormat = paCustomFormat


class AudioWaveState(enum.Enum):
    """Enums for State corresponding with the pyAudio"""

    Continue = paContinue
    Complete = paComplete
    Abort = paAbort


class AudioWaveEvent(enum.Enum):
    Repeated = 1


class AudioWaveFrames(list):
    def __init__(
        self,
        channels: int = 1,
        sample_size: int = 1,
        rate: int = 441000,
        frames: list[bytes] = [],
        bytes: bytes = b"",
        frames_per_buffer: int = 1024,
    ):
        super().__init__(frames)

        # for geting the next frames
        self.read = 0

        self.channels = channels
        self.sample_size = sample_size
        self.rate = rate
        self.frames_per_buffer = frames_per_buffer

        if bytes:
            self.load_bytes(bytes, frames_per_buffer)

    def add(self, data: bytes):
        """add bytes to the frames"""
        self.append(data)

    @property
    def size(self) -> int:
        return len(self.bytes)

    @property
    def frame_count(self) -> int:
        return len(self)

    def load_wave(self, wave_read: Wave_read, frames_per_buffer: int) -> None:
        """reads the frames from a wave.Wave_read object"""

        self.clear()  # deletes the frames

        self.channels = wave_read.getnchannels()
        self.rate = wave_read.getframerate()

        while True:  # reads until empty
            data = wave_read.readframes(frames_per_buffer)

            if data:
                self.add(data)
            else:
                break

        wave_read.rewind()

    def load_bytes(self, bytes: bytes, frames_per_buffer: int) -> int:
        """reads the frames from a bytes object"""

        self.clear()  # deletes the frames
        read = 0
        size = len(bytes)
        while self.size != size:
            data = bytes[read : read + frames_per_buffer]
            if data:
                self.add(data)
                read += frames_per_buffer
            else:
                break

    @classmethod
    def save_frames(
        cls,
        frames: "AudioWaveFrames",
        file: str,
        channels: int,
        sample_size: int,
        rate: int,
    ):
        wave_write = Wave_write(file)
        wave_write.setnchannels(channels)
        wave_write.setsampwidth(sample_size)
        wave_write.setframerate(rate)
        wave_write.writeframes(frames.bytes)
        wave_write.close()

    @property
    def bytes(self) -> bytes:
        return b"".join(self)

    def save(self, file: str):
        self.save_frames(self, file, self.channels, self.sample_size, self.rate)

    def next_frame(self):
        if self.read < len(self):
            data = self[self.read]
            self.read += 1
            return data

    def rewind(self):
        self.read = 0


class AudioWaveFrameBase:
    def __init__(self):
        self._frames: AudioWaveFrames = AudioWaveFrames()

    @property
    def frames(self):
        return self._frames

    @property
    def bytes(self) -> bytes:
        return self._frames.bytes

    def clear(self):
        self._frames.clear()


class AudioWaveStream(Stream, AudioWaveFrameBase):
    def __init__(
        self,
        pa: PyAudio,
        format: AudioWaveFormat = AudioWaveFormat.Int16,
        channels: int = 2,
        rate: int = 44400,
        mode=0,
        frames_per_buffer: int = 1024,
        input_device_index: int = None,
        output_device_index: int = None,
        start: bool = False,
    ):

        self._mode: int = mode

        Stream.__init__(
            self,
            pa,
            format=format.value,
            channels=channels,
            rate=rate,
            output=not bool(mode),
            input=bool(mode),
            frames_per_buffer=frames_per_buffer,
            input_device_index=input_device_index,
            start=start,
            output_device_index=output_device_index,
        )
        AudioWaveFrameBase.__init__(self)

    def get_read_loop(self, seconds) -> int:
        if seconds:
            return int(self._rate / self._frames_per_buffer * seconds)
        else:
            return -1

    def read(self, buffer_size=0) -> bytes:
        buffer_size = buffer_size or self._frames_per_buffer
        frame = super().read(buffer_size)
        self.frames.add(frame)
        return frame

    def write(self, data, *args):
        self.frames.add(data)
        return super().write(data, *args)

    @property
    def _sample_size(self):
        return self.parent.get_sample_size(self._format)

    @property
    def parent(self) -> "AudioWave":
        return self._parent

    def save_frames(self, frames: AudioWaveFrames, file: str) -> int:
        AudioWaveFrames.save_frames(
            frames, file, self._channels, self._sample_size, self._rate
        )
        return len(frames)

    def save_to_file(self, file: str):
        return self.save_frames(self.bytes, file)


class AudioWave(PyAudio):
    def __init__(self):
        super().__init__()

    @property
    def streams(self) -> List:
        return list(self._streams)

    def open(self, *args, **kwargs):

        stream = AudioWaveStream(self, *args, **kwargs)
        self._streams.add(stream)
        return stream

    def get_format_from_width(self, width):
        format = super().get_format_from_width(width)
        return AudioWaveFormat(format)


class AudioWaveBase(AudioWaveFrameBase):
    AUDIOWAVE: AudioWave = None

    def __init__(self, callback=None, **kwargs):
        AudioWaveFrameBase.__init__(self)

        if not AudioWaveBase.AUDIOWAVE:
            AudioWaveBase.AUDIOWAVE = AudioWave()

        self.stream: AudioWaveStream = None
        self._pause = True
        self.callback = callback
        self.kwargs = kwargs

        if kwargs:
            self.create_stream(**kwargs)

    def set_frames(self, frames: AudioWaveFrames):
        self._frames = frames

    def pause(self):
        self._pause = True

    def resume(self):
        self._pause = False

    @property
    def rate(self):
        return self.stream._rate

    def write(self, data: bytes):
        try:
            if self.stream:
                return self.stream.write(data)
        except:
            if self.callback:
                self.callback(error=AudioWaveError.Write)

    def read(self, buffer_size):
        try:
            if self.stream:
                return self.stream.read(buffer_size)
        except:
            if self.callback:
                self.callback(error=AudioWaveError.Read)

    @property
    def frames_per_buffer(self):
        if self.stream:
            return self.stream._frames_per_buffer
        return 0

    @property
    def stream_frames(self):
        if self.stream:
            return self.stream._frames
        return 0

    def create_stream(self, **kwargs):
        self.stream = self.core.open(**kwargs)

    def recreate_stream(self):
        self.stream.close()
        self.stream = None
        self.start_stream()

    def close_stream(self):
        self.pause()
        if self.stream:
            try:
                self.stop_stream()
                self.stream.close()
            except:
                if self.callback:
                    self.callback(error=AudioWaveError.Close)
            self.stream = None

    def start_stream(self):
        try:
            if not self.stream:
                self.create_stream(**self.kwargs)
            self.stream.start_stream()
        except:
            if self.callback:
                self.callback(error=AudioWaveError.Create)

    @property
    def core(self) -> AudioWave:
        return AudioWaveBase.AUDIOWAVE

    def stop_stream(self):
        try:
            if self.stream:
                return self.stream.stop_stream()
        except:
            if self.callback:
                self.callback(error=AudioWaveError.Stop)

    def close(self):
        self.close_stream()
        self.core.terminate()

    def save_frames(self, *args):
        if self.stream:
            return self.stream.save_frames(*args)

    def save_to_file(self, file: str):
        self.save_frames(file, self.bytes)


class AudioWavePlayer(AudioWaveBase):
    def load_file(self, file: io.FileIO):
        wave_read = Wave_read(file)
        format = self.core.get_format_from_width(wave_read.getsampwidth())
        channels = wave_read.getnchannels()
        rate = wave_read.getframerate()

        self.create_stream(format=format, channels=channels, rate=rate)

        self.frames.load_wave(
            wave_read=wave_read, frames_per_buffer=self.frames_per_buffer
        )

    def play(self, block=True, **kwargs):
        if block:
            return self._play(**kwargs)
        else:
            threading.Thread(target=self._play, kwargs=kwargs).start()

    def _play(
        self,
        file=None,
        frames: AudioWaveFrames = None,
        bytes: bytes = b"",
        loop: bool = False,
        repeat: int = 0,
        resume: bool = False,
    ):
        """
        :param:loop: whether to loop the playing.
        :type:bool: whether to loop the playing.
        :param:repeat: number of times to repeat the playing.
        """

        if file:
            self.load_file(file)

        self.start_stream()

        if bytes:
            frames = AudioWaveFrames(
                channels=self.stream._channels,
                sample_size=self.stream._sample_size,
                rate=self.stream._rate,
                bytes=bytes,
                frames_per_buffer=self.frames_per_buffer,
            )

        frames = frames or self.frames

        if loop and repeat:
            repeat = 0

        if resume:
            self._pause = False

        while not self._pause:
            rd_data = frames.next_frame()

            if rd_data:
                self.write(rd_data)

                if self.callback:
                    self.callback(state=AudioWaveState.Continue)

            else:
                frames.rewind()
                if loop or repeat:
                    if repeat:
                        repeat -= 1

                    continue
                else:
                    break

        if self.callback:
            self.callback(state=AudioWaveState.Complete)

        self.close_stream()

    def play_frames(self, frames: AudioWaveFrames, **kwargs):
        self.play(frames=frames, **kwargs)


class AudioWaveRecorder(AudioWaveBase):
    def __init__(self, **kwargs):
        super().__init__(mode=1, **kwargs)

    def get_read_loop(self, seconds) -> int:
        return self.stream.get_read_loop(seconds)

    def record(self, block=True, **kwargs):
        if block:
            return self._record(**kwargs)
        else:
            threading.Thread(target=self._record, kwargs=kwargs).start()

    def _record(
        self, buffer_size=1024, seconds=0, add=True, file=None
    ) -> AudioWaveFrames:
        self.start_stream()

        loop = self.get_read_loop(seconds)

        frames = AudioWaveFrames(
            channels=self.stream._channels,
            sample_size=self.stream._sample_size,
            rate=self.stream._rate,
            frames_per_buffer=self.frames_per_buffer,
        )

        while not self._pause:
            frame = self.read(buffer_size)
            if frame:
                frames.add(frame)
                if self.callback:
                    self.callback(
                        frame=frame, frames=frames, state=AudioWaveState.Continue
                    )

                if loop >= 0:
                    loop -= 1
                    if loop < 0:
                        break
            else:
                break

        if add:
            self.frames.extend(frames)
        else:
            self.set_frames(frames)

        if self.callback:
            self.callback(frames=frames, state=AudioWaveState.Complete)

        if file and frames:
            self.save_frames(frames, file)

        self.close_stream()
        return frames

    @property
    def bytes(self) -> AudioWaveFrames:
        return self.stream.bytes


if __name__ == "__main__":
    player = AudioWavePlayer()
    player.play(file="path_of_file.wav", repeat=1)
    # player.play(bytes=bytes)

    # recorder = AudioWaveRecorder(file="path_of_file.wav")
    # recorder.record(seconds=0)
