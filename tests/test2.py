import ss

from datetime import timedelta
from prmp_qt import *
from audiolivewaveform import *


class Button(IconTextButton):
    def __init__(self, icon: str, func):
        super().__init__(
            icon=r"C:\Users\Administrator\Desktop\GITHUB_PROJECTS\Amebo\desktop\ui\utils\resources\%s.svg"
            % icon,
            icon_size=30,
            togglable=1,
            iconColor="white",
        )
        self.clicked.connect(func)


class Win(QWidget):
    def __init__(self):
        super().__init__()

        lay = QVBoxLayout(self)

        waveFormChannel1 = AudioWaveFormChannel(
            options=AudioWaveFormOptions(
                gravity=AudioWaveFormGravity.Average,
                pixelWidth=5,
                pixelSpacing=1,
                radius=3,
                showHLine=0,
                zoom=0.85,
            )
        )
        waveFormChannel2 = AudioWaveFormChannel(
            options=AudioWaveFormOptions(
                gravity=AudioWaveFormGravity.Average,
                pixelWidth=5,
                pixelSpacing=1,
                radius=3,
                showHLine=0,
            )
        )
        m = 2
        margins = QMargins(m, m, m, m)

        liveWaveFormChannel1 = LiveAudioWaveFormChannel(
            samplesPerPixel=1000, interval=50, preOffset=0
        )
        liveWaveFormChannel1.startedSignal.connect(self.playing_wave_form_started)
        liveWaveFormChannel1.stoppedSignal.connect(self.playing_wave_form_stopped)

        liveWaveFormChannel2 = LiveAudioWaveFormChannel(
            samplesPerPixel=1000, interval=50, preOffset=0
        )

        file="assets/test_stereo.wav"
        self.playing = PlayingAudioWaveForm(
            waveFormChannel1=waveFormChannel1,
            waveFormChannel2=waveFormChannel2,
            margins=margins,
            liveWaveFormChannel1=liveWaveFormChannel1,
            liveWaveFormChannel2=liveWaveFormChannel2,
        )
        lay.addWidget(self.playing)

        aw = self.playing.audiowave
        aw.open(file=file)
        self.playing.live.createAudio(
            rate=aw.frame_rate,
            channels=aw.channels,
            sampleWidth=aw.sample_width,
        )
        min, max = aw.channel_min_max_real_array(1)
        liveWaveFormChannel1.setMinMax(min, max)
        min2, max2 = aw.channel_min_max_real_array(1)
        liveWaveFormChannel2.setMinMax(min2, max2)

        waveFormChannel1 = AudioWaveFormChannel(
            minimums=min,
            maximums=max,
            options=AudioWaveFormOptions(
                gravity=AudioWaveFormGravity.Average,
                pixelWidth=5,
                pixelSpacing=1,
                radius=3,
                showHLine=0,
                zoom=0.8,
                seekColor=QColor("orange"),
                seekerColor=Qt.yellow,
                seekerRadius=10,
            ),
        )
        waveFormChannel2 = AudioWaveFormChannel(
            minimums=min2,
            maximums=max2,
            options=AudioWaveFormOptions(
                gravity=AudioWaveFormGravity.Average,
                pixelWidth=5,
                pixelSpacing=1,
                radius=3,
                showHLine=0,
                zoom=0.8,
                seekColor=QColor("orange"),
                seekerColor=Qt.yellow,
                seekerRadius=10,
            ),
        )
        self.fixed_wave_form = FixedLiveAudioWaveForm(
            margins=margins,
            waveFormChannel1=waveFormChannel1,
            waveFormChannel2=waveFormChannel2,
        )

        lay.addWidget(self.fixed_wave_form)

        but_lay = QHBoxLayout()
        lay.addLayout(but_lay)

        self.btn_play = Button("player-play", self.play)
        but_lay.addWidget(self.btn_play)

        self.btn_pause = Button("player-pause", self.playing.pauseLive)
        but_lay.addWidget(self.btn_pause)

        self.btn_stop = Button("player-stop", self.playing.stopLive)
        but_lay.addWidget(self.btn_stop)

        self.playing.stateSignal.connect(self.stateSignalReceiver)

        self.stateSignalReceiver(0)

    def stateSignalReceiver(self, state: int):
        self.btn_play.setEnabled(state not in [1, 2])
        self.btn_pause.setEnabled(state in [1, 2])
        self.btn_stop.setEnabled(state != 0)

    def seconds_update(self, seconds: int):
        td = timedelta(seconds=seconds)
        td = str(td).zfill(8)
        self.time_label.setText(td)

    def recorder_state(self, state: int):
        if state == 1:  # start
            self.playing.setDisabled(True)

        elif state == 2:  # resume
            ...

        elif state == 3:  # pause
            ...

        else:  # stop
            self.playing.byteArray = self.recorder.byteArray
            self.playing.setEnabled(True)

    def player_state(self, state: int):
        if state == 1:  # start
            self.recorder.setDisabled(True)
            # print("player start")
            self.play_wave_form.resetWaveForm()
            self.fixed_wave_form.resetWaveForm()
        elif state == 2:  # resume
            # print("player resume")
            ...
        elif state == 3:  # pause
            # print("player paused")
            ...
        else:  # stop
            self.recorder.setEnabled(True)
            # self.playing.live.byteArray = b""
            # print("player stopped")

        if state in (1, 2):
            self.play_wave_form.startWaveForm()
            self.fixed_wave_form.startWaveForm()
            # elif not state:
            ...
        else:
            self.play_wave_form.stopWaveForm()
            self.fixed_wave_form.stopWaveForm()
            ...

    def playing_wave_form_started(self):
        # print("waveform started")
        ...

    def playing_wave_form_stopped(self):
        # print("waveform stopped")
        # print("waveform-time=", time() - self.time)
        # a.quit()
        ...

    def play(self):
        audiowave = self.playing.audiowave

        # ---

        duration = audiowave.duration
        print(duration)
        self.play_wave_form.liveWaveFormChannel1.syncIntervalAndSamplesPerPixelWithDuration(
            duration
        )
        self.play_wave_form.liveWaveFormChannel2.syncIntervalAndSamplesPerPixelWithDuration(
            duration
        )
        self.fixed_wave_form.setSeconds(duration)

        # ---

        self.playing.startLive()


if __name__ == "__main__":
    a = QApplication()
    
    a.setStyleSheet(
        """
        AudioWaveForm {
                border: 3px solid #0000de;
                border-radius: 5px;
                min-height: 100px;
                min-width: 400px;
            }
        Label {
            background: #0000de;
            color: white;
            border-radius: 5px;
            font-weight: bold;
            font-family: Times New Roman;
            font-size: 20px;
            max-height: 25px;
        }
        LeftAlignLabel {
            padding-left: 1px;
        }
        Label#time_label {
            font-size: 35px;
            max-height: 40px;
        }
        Button {
            border: none;
            border-radius: 5px;
            background: #000078;
        }
        Button:hover {
            background: #000096;
        }
        Button:pressed {
            background: #0000b4;
        }
        Button:disabled {
            background: red;
        }

        PlayingAudioWaveForm, FixedLiveAudioWaveForm {
            border-color: #de00de;
        }
        Player Label {
            background: #de00de;
        }
        Player Button {
            background: #780078;
        }
        Player Button:hover {
            background: #b400b4;
        }
        Player Button:pressed {
            background: #960096;
        }
        """
    )

    w = Win()
    w.show()
    a.exec()
