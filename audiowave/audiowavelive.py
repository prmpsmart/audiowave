from audiowave import *
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QTimer, Signal
from PySide6.QtMultimedia import QAudio, QAudioSink, QAudioSource, QAudioFormat


class AudioWaveBuffer(QBuffer):
    readSignal = Signal(float)
    writtenSignal = Signal(float)

    def __init__(self):
        super().__init__()

        self.read_data = 0
        self.written_data = 0

    def readData(self, maxlen: int):
        read = super().readData(maxlen)
        self.read_data += len(read)
        self.readSignal.emit(self.read_data / len(self.buffer().data()))
        return read

    def writenData(self, data: bytes, len_: int):
        self.written_data += len_
        self.writtenSignal.emit(self.written_data)
        return super().writeData(data, len_)


class LiveAudioWave:
    def __str__(self) -> str:
        return self.__class__.__name__

    def __init__(
        self,
        input: bool,
        log=False,
        stateReceiver: typing.Callable[[QAudio.State], None] = None,
        **kwargs,
    ) -> None:

        self.log = log
        self.stateReceiver = stateReceiver

        self.byteArray = QByteArray()
        self.audio: typing.Union[QAudioSource, QAudioSink] = None
        self.audioClass = QAudioSource if input else QAudioSink

        self.createAudio(**kwargs)

    @property
    def state(self) -> QAudio.State:
        if self.audio:
            return self.audio.state()

    @property
    def sampleFormat(self) -> QAudioFormat.SampleFormat:
        return self.audioFormat.sampleFormat()

    @property
    def sampleWidth(self) -> int:
        if self.sampleFormat == QAudioFormat.UInt8:
            return 1
        elif self.sampleFormat == QAudioFormat.Int16:
            return 2
        elif self.sampleFormat == QAudioFormat.Int32:
            return 3
        elif self.sampleFormat == QAudioFormat.Float:
            return 4
        elif self.sampleFormat == QAudioFormat.NSampleFormats:
            return 5
        else:
            return 0

    @classmethod
    def getFormatFromWidth(cls, width) -> QAudioFormat.SampleFormat:
        if width == 1:
            return QAudioFormat.UInt8
        elif width == 2:
            return QAudioFormat.Int16
        elif width == 3:
            return QAudioFormat.Int32
        elif width == 4:
            return QAudioFormat.Float
        elif width == 5:
            return QAudioFormat.NSampleFormats
        else:
            return QAudioFormat.Unknown

    def getAudioFormat(
        self,
        rate: int = 44100,
        channels: int = 1,
        sampleFormat: QAudioFormat.SampleFormat = QAudioFormat.Int16,
        sampleWidth: int = 0,
    ) -> None:
        audioFormat = QAudioFormat()
        audioFormat.setSampleRate(rate)
        audioFormat.setChannelCount(channels)
        if sampleWidth:
            sampleFormat = self.getFormatFromWidth(sampleWidth)
        audioFormat.setSampleFormat(sampleFormat)

        return audioFormat

    def createAudio(self, **kwargs):
        if self.audio:
            self.audio.deleteLater()
            self.audio = None

        audioFormat = self.getAudioFormat(**kwargs)
        self.audio = self.audioClass(audioFormat)
        self.audio.stateChanged.connect(self.__stateChanged)

    def __stateChanged(self, newState: QAudio.State):
        if newState == QAudio.State.ActiveState:
            if self.log:
                print(f"{self} Session Started ...")

        elif newState == QAudio.State.IdleState:
            ...

        elif newState == QAudio.State.SuspendedState:
            if self.log:
                print(f"{self} Session Suspended")

        elif newState == QAudio.State.StoppedState:

            if self.log:
                print(f"{self} Session Ended ...")

        if self.stateReceiver:
            self.stateReceiver(newState)

    @property
    def channels(self) -> int:
        return self.audioFormat.channelCount()

    @property
    def audioFormat(self) -> QAudioFormat:
        return self.audio.format()

    @property
    def isInput(self) -> bool:
        return isinstance(self.audio, QAudioSource)

    @property
    def rate(self) -> int:
        return self.audioFormat.sampleRate()

    @property
    def bytes(self) -> bytes:
        return self.data

    @property
    def volume(self) -> int:
        self.audio.volume()

    @property
    def active(self):
        return self.state == QAudio.State.ActiveState

    @property
    def idle(self):
        return self.state == QAudio.State.IdleState

    @property
    def suspended(self):
        return self.state == QAudio.State.SuspendedState

    @property
    def stopped(self):
        return self.state == QAudio.State.StoppedState

    def setVolume(self, volume: int):
        self.audio.setVolume(volume)

    def duration(self, bytes: bytes = b"") -> int:
        size = len(bytes)
        rate = self.rate
        duration = size / rate / 2
        return duration

    def reset(self):
        self.audio.reset()

    def resume(self):
        self.audio.resume()

    def suspend(self):
        self.audio.suspend()

    def pause(self):
        self.suspend()

    def stop(self):
        self.audio.stop()

    def start(self, byteArray: QByteArray = b"", new: bool = False) -> QByteArray:
        byteArray = QByteArray(byteArray or self.byteArray)
        buffer = QBuffer(byteArray)
        openMode = QIODevice.ReadWrite
        if new:
            buffer.setData(b"")
        elif self.isInput:
            openMode = QIODevice.Append
        buffer.open(openMode)
        self.audio.start(buffer)

        self.byteArray = byteArray
        if self.isInput:
            return byteArray


class AudioWaveRecorder(LiveAudioWave):
    def __init__(self, **kwargs) -> None:
        super().__init__(True, **kwargs)

    def save(self, file: str):
        bytes = self.bytes
        if bytes:
            wave_write = wave.Wave_write(file)
            wave_write.setnchannels(self.channels)
            wave_write.setsampwidth(self.sampleWidth)
            wave_write.setframerate(self.rate)
            wave_write.writeframes(bytes)
            wave_write.close()

    def record(self, **kwargs) -> QByteArray:
        return self.start(**kwargs)


class AudioWavePlayer(LiveAudioWave):
    def __init__(self, **kwargs) -> None:
        super().__init__(False, **kwargs)

    def play(self, byteArray: QByteArray = b"", file: str = ""):
        if file:
            wave_read = wave.Wave_read(file)
            channels = wave_read.getnchannels()
            sampleWidth = wave_read.getsampwidth()
            rate = wave_read.getframerate()
            byteArray = wave_read._data_chunk.read()
            wave_read.close()

            self.createAudio(
                channels=channels,
                sampleWidth=sampleWidth,
                rate=rate,
            )

        self.start(byteArray)


class LiveAudioWaveTimer(QTimer):
    def __init__(self, callback: typing.Callable[[None], None]) -> None:
        super().__init__()

        self.callback = callback

        self.seconds: int = 0
        self.setInterval(990)
        self.timeout.connect(self.count_down)

    def count_down(self):
        self.seconds += 1
        if self.callback:
            self.callback(self.seconds)

    def reset(self) -> None:
        self.seconds = 0


class TimedLiveAudioWave:
    stateSignal = Signal(int)
    secondsSignal = Signal(int)

    def __init__(self, input: bool, **kwargs) -> None:
        LIVE = AudioWaveRecorder if input else AudioWavePlayer
        self.live = LIVE(stateReceiver=self.stateReceiver, **kwargs)
        self.timer = LiveAudioWaveTimer(self.secondsSignal.emit)
        self.suspended = 1

    @property
    def byteArray(self):
        return self.live.byteArray

    @byteArray.setter
    def byteArray(self, byteArray: QByteArray):
        self.live.byteArray = byteArray

    def stateReceiver(self, state: QAudio.State):
        if state == QAudio.ActiveState:
            self.timer.start()
            self.stateSignal.emit(1 + self.suspended)
            self.suspended = 0

        elif state == QAudio.SuspendedState:
            self.timer.stop()
            self.suspended = 1
            self.stateSignal.emit(3)

        elif state in [QAudio.StoppedState, QAudio.IdleState]:
            self.timer.stop()
            self.timer.reset()
            self.stateSignal.emit(0)

    def startLive(self):
        if self.live.suspended:
            self.live.resume()

        else:
            self.goLive()

    def goLive(self):
        ...

    def pauseLive(self):
        if self.live.active:
            self.live.pause()

    def stopLive(self):
        if not self.live.stopped:
            self.live.stop()


class TimedLiveAudioWavePlayer(TimedLiveAudioWave):
    def __init__(self) -> None:
        super().__init__(False)


class TimedLiveAudioWaveRecorder(TimedLiveAudioWave):
    def __init__(self) -> None:
        super().__init__(True)


if __name__ == "__main__":
    app = QGuiApplication()

    recorder = AudioWaveRecorder(log=1)
    byteArray = recorder.record()

    def quit(state):
        if state != QAudio.State.ActiveState:
            app.quit()

    player = AudioWavePlayer(stateReceiver=quit, log=1)

    def record():
        recorder.stop()
        player.play(byteArray=byteArray)

    QTimer.singleShot(5000, record)

    app.exec()
