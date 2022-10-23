from audiowavelive import *
from audiowaveform import *


class TimedLiveAudioWaveForm(TimedLiveAudioWave):
    def __init__(self, input: bool) -> None:
        TimedLiveAudioWave.__init__(self, input)

        self.audiowave = AudioWave()

        self.stateSignal.connect(self.stateSignalReceiver)
        self.secondsSignal.connect(self.secondsUpdate)

        self.stateSignalReceiver(0)

    def stateSignalReceiver(self, state: int):
        if state in (1, 2):
            self.startWaveForm()
        else:
            self.stopWaveForm()

    def secondsUpdate(self, seconds: int):
        ...

    def startWaveForm(self):
        ...

    def stopWaveForm(self):
        ...


class PlayingAudioWaveForm(LiveAudioWaveForm, TimedLiveAudioWaveForm):
    def __init__(self, **kwargs) -> None:
        LiveAudioWaveForm.__init__(self, **kwargs)
        TimedLiveAudioWaveForm.__init__(self, False)


class RecordingAudioWaveForm(TimedLiveAudioWaveForm, LiveAudioWaveForm):
    def __init__(self, **kwargs) -> None:
        LiveAudioWaveForm.__init__(self, **kwargs)
        TimedLiveAudioWaveForm.__init__(self, True)




class PlayingFixedAudioWaveForm(TimedLiveAudioWaveForm, FixedLiveAudioWaveForm):
    def __init__(
        self,
        file: str = "",
        bytes: bytes = "",
        with_header: bool = False,
        channels: int = 1,
        **kwargs
    ) -> None:
        FixedLiveAudioWaveForm.__init__(self, **kwargs)
        TimedLiveAudioWaveForm.__init__(self, False)
        if file or bytes:
            self.audiowave.open(
                file=file, bytes=bytes, with_header=with_header, channels=channels
            )
            self.live.byteArray = bytes

    def goLive(self):
        self.live.play()
