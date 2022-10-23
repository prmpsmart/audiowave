import ss

from datetime import timedelta
from prmp_qt import *
from audiowavelive import *
from audiowaveform import *
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


class LiveFrame(TimedLiveAudioWave, VFrame):
    def __init__(self, input: bool) -> None:
        VFrame.__init__(self)
        TimedLiveAudioWave.__init__(self, input)

        lay = self.layout()
        lay.setSpacing(5)

        m = 2
        lay.setContentsMargins(m, m, m, m)

        self.audiowave = AudioWave()

        lay.addWidget(LeftAlignLabel(text=self.__class__.__name__ + " :"))

        self.time_label = AlignLabel(text="00:00:00", name="time_label")
        lay.addWidget(self.time_label)

        self.but_lay = QHBoxLayout()
        lay.addLayout(self.but_lay)

        self.btn_play = Button("player-play", self.startLive)
        self.but_lay.addWidget(self.btn_play)

        self.btn_pause = Button("player-pause", self.pauseLive)
        self.but_lay.addWidget(self.btn_pause)

        self.btn_stop = Button("player-stop", self.stopLive)
        self.but_lay.addWidget(self.btn_stop)

        self.stateSignal.connect(self.stateSignalReceiver)
        self.secondsSignal.connect(self.seconds_update)

        self.stateSignalReceiver(0)

    def stateSignalReceiver(self, state: int):
        self.btn_play.setEnabled(state not in [1, 2])
        self.btn_pause.setEnabled(state in [1, 2])
        self.btn_stop.setEnabled(state != 0)

    def seconds_update(self, seconds: int):
        td = timedelta(seconds=seconds)
        td = str(td).zfill(8)
        self.time_label.setText(td)


class Player(LiveFrame):
    def __init__(self) -> None:
        LiveFrame.__init__(self, False)

    def goLive(self):
        self.live.play()


class Recorder(LiveFrame):
    def __init__(self) -> None:
        LiveFrame.__init__(self, True)

        self.btn_play.deleteLater()
        self.btn_play = Button("microphone", self.startLive)
        self.but_lay.insertWidget(0, self.btn_play)

    def go_live(self):
        self.live.record()


class LiveAudioWaveWindow(HFrame):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.setWindowTitle(f"Audio Wave")
        lay = self.layout()

        m = 2
        lay.setContentsMargins(m, m, m, m)

        self.recorder = Recorder()
        self.recorder.stateSignal.connect(self.recorder_state)
        lay.addWidget(self.recorder)

        self.player = Player()
        self.player.stateSignal.connect(self.player_state)
        lay.addWidget(self.player)

    def recorder_state(self, state: int):
        if state == 1:  # start
            self.player.setDisabled(True)

        elif state == 2:  # resume
            ...

        elif state == 3:  # pause
            ...

        else:  # stop
            self.player.byteArray = self.recorder.byteArray
            self.player.setEnabled(True)

    def player_state(self, state: int):
        if state == 1:  # start
            self.recorder.setDisabled(True)

        elif state == 2:  # resume
            ...

        elif state == 3:  # pause
            ...

        else:  # stop
            self.recorder.setEnabled(True)


class ColorButton(QPushButton):
    colorChanged = Signal()

    def __init__(self) -> None:
        super().__init__()

        self.colorDialog = QColorDialog()
        self.clicked.connect(self.colorDialog.show)
        self.colorDialog.currentColorChanged.connect(self.setColor)

    def setColor(self, color: QColor):
        name = color.name()
        self.setText(name)
        self.setStyleSheet(f"background: {name};")
        self.colorChanged.emit()


class ChannelOptions(QGroupBox):
    def __init__(self, options: "Options", num=1):
        super().__init__(f"Channel {num}")

        w = 220
        self.setMinimumWidth(w)
        self.setMaximumWidth(w)
        self.num = num

        form = QFormLayout(self)

        self.options = options

        self.visible = QCheckBox()
        form.addRow("Visible : ", self.visible)

        self.background = ColorButton()
        form.addRow("Background : ", self.background)

        self.pixelSpacing = QSpinBox()
        form.addRow("Pixel Spacing : ", self.pixelSpacing)

        self.pixelWidth = QSpinBox()
        form.addRow("Pixel Width : ", self.pixelWidth)

        self.zoom = QDoubleSpinBox()
        form.addRow("Zoom : ", self.zoom)

        self.scale = QSpinBox()
        form.addRow("Scale : ", self.scale)

        self.avgColor = ColorButton()
        form.addRow("Avg Color : ", self.avgColor)

        self.minColor = ColorButton()
        form.addRow("Min Color : ", self.minColor)

        self.maxColor = ColorButton()
        form.addRow("Max Color : ", self.maxColor)

        self.radius = QSpinBox()
        form.addRow("Radius : ", self.radius)

        self.grid = QSpinBox()
        form.addRow("Grid : ", self.grid)

        self.emptyPixelHeight = QSpinBox()
        form.addRow("Empty Pixel Height : ", self.emptyPixelHeight)

        self.showHLine = QCheckBox()
        form.addRow("Show HLine : ", self.showHLine)

        self.gridColor = ColorButton()
        form.addRow("Grid Color : ", self.gridColor)

        self.seekColor = ColorButton()
        form.addRow("Seek Color : ", self.seekColor)

        self.seekerColor = ColorButton()
        form.addRow("Seeker Color : ", self.seekerColor)

        self.seekerRadius = QSpinBox()
        form.addRow("Seeker Radius : ", self.seekerRadius)

        self.gravity = QComboBox()
        form.addRow("Gravity : ", self.gravity)

        self.preOffset = QCheckBox()
        form.addRow("Pre-Offset : ", self.preOffset)

        self.pauseOnEnd = QCheckBox()
        form.addRow("Pause On End : ", self.pauseOnEnd)

        for name in AudioWaveFormGravity._member_names_:
            self.gravity.addItem(name, AudioWaveFormGravity[name])

        wids = [
            self.visible,
            self.background,
            self.pixelSpacing,
            self.pixelWidth,
            self.zoom,
            self.scale,
            self.avgColor,
            self.minColor,
            self.maxColor,
            self.radius,
            self.grid,
            self.emptyPixelHeight,
            self.showHLine,
            self.gridColor,
            self.seekColor,
            self.seekerColor,
            self.seekerRadius,
            self.gravity,
            self.preOffset,
            self.pauseOnEnd,
        ]

        for wid in wids:
            cls = type(wid)
            signal: SignalInstance = None
            if cls == QCheckBox:
                signal = wid.toggled

            elif cls == ColorButton:
                signal = wid.colorChanged

            elif cls in [QSpinBox, QDoubleSpinBox]:
                signal = wid.valueChanged

            elif cls == QComboBox:
                signal = wid.currentIndexChanged

            if signal:
                signal.connect(self.updateWaveForm)

        self.visible.toggle()

    def updateWaveForm(self):
        sender = self.sender()
        p = self.options._window.play_wave_form
        fx = self.options._window.fixed_wave_form
        f = o = None
        if self.num == 1:
            l = p.liveWaveFormChannel1
            if p.waveFormChannel1:
                o = p.waveFormChannel1.options
            if fx.waveFormChannel1:
                f = fx.waveFormChannel1.options
        else:
            l = p.liveWaveFormChannel2
            if p.waveFormChannel2:
                o = p.waveFormChannel2.options
            if fx.waveFormChannel2:
                f = fx.waveFormChannel2.options

        value = None
        if isinstance(sender, QCheckBox):
            value = sender.isChecked()

        elif isinstance(sender, ColorButton):
            value = sender.text()

        elif isinstance(sender, (QSpinBox, QDoubleSpinBox)):
            value = sender.value()

        elif isinstance(sender, QComboBox):
            value = sender.currentData()

        if value == None:
            return

        for a in (o, f):
            if a:
                if sender == self.visible:
                    a.setVisible(value)
                elif sender == self.background:
                    a.setBackground(value)
                elif sender == self.pixelSpacing:
                    a.setPixelSpacing(value)
                elif sender == self.pixelWidth:
                    a.setPixelWidth(value)
                elif sender == self.zoom:
                    a.setZoom(value)
                elif sender == self.scale:
                    a.setScale(value)
                elif sender == self.avgColor:
                    a.setAvgColor(value)
                elif sender == self.minColor:
                    a.setMinColor(value)
                elif sender == self.maxColor:
                    a.setMaxColor(value)
                elif sender == self.radius:
                    a.setRadius(value)
                elif sender == self.grid:
                    a.setGrid(value)
                elif sender == self.emptyPixelHeight:
                    a.setEmptyPixelHeight(value)
                elif sender == self.showHLine:
                    a.setShowHLine(value)
                elif sender == self.gridColor:
                    a.setGridColor(value)
                elif sender == self.seekColor:
                    a.setSeekColor(value)
                elif sender == self.seekerColor:
                    a.setSeekerColor(value)
                elif sender == self.seekerRadius:
                    a.setSeekerRadius(value)
                elif sender == self.gravity:
                    a.setGravity(value)

        if l:
            if sender == self.preOffset:
                if l.preOffset != value:
                    l.preOffset = value
            elif sender == self.pauseOnEnd:
                if l.pauseOnEnd != value:
                    l.pauseOnEnd = value


class Options(HFrame):
    def __init__(self, window: "LiveAudioWaveFormWindow", **kwargs):
        super().__init__(**kwargs)
        self._window = window
        lay = self.layout()

        channel1 = ChannelOptions(self)
        lay.addWidget(channel1)

        channel2 = ChannelOptions(self, 2)
        lay.addWidget(channel2)


class LiveAudioWaveFormWindow(LiveAudioWaveWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

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

        self.record_wave_form = RecordingAudioWaveForm(
            waveFormChannel1=waveFormChannel1, margins=margins
        )
        self.recorder.layout().insertWidget(1, self.record_wave_form)
        self.recorder.hide()

        audiowave = self.player.audiowave
        audiowave.open("assets/test_stereo.wav")
        # audiowave.open("assets/test_mono.wav")
        self.player.live.createAudio(
            rate=audiowave.frame_rate,
            channels=audiowave.channels,
            sampleWidth=audiowave.sample_width,
        )

        self.player.live.byteArray = audiowave.bytes
        # self.player.live.byteArray = b"abokede segun" * 5000
        audiowave.open(bytes=self.player.live.byteArray, with_header=0)

        min, max = audiowave.channel_min_max_real_array(1)
        liveWaveFormChannel1 = LiveAudioWaveFormChannel(minimums=min, maximums=max,
            samplesPerPixel=1000, interval=50, preOffset=0
        )
        liveWaveFormChannel1.startedSignal.connect(self.playing_wave_form_started)
        liveWaveFormChannel1.stoppedSignal.connect(self.playing_wave_form_stopped)

        min2, max2 = audiowave.channel_min_max_real_array(1)
        liveWaveFormChannel2 = LiveAudioWaveFormChannel(minimums=min2, maximums=max2,
            samplesPerPixel=1000, interval=50, preOffset=0
        )

        self.play_wave_form = PlayingAudioWaveForm(
            waveFormChannel1=waveFormChannel1,
            # waveFormChannel2=waveFormChannel2,
            margins=margins,
            liveWaveFormChannel1=liveWaveFormChannel1,
            # liveWaveFormChannel2=liveWaveFormChannel2,
        )
        self.player.layout().insertWidget(1, self.play_wave_form)
        self.player.btn_play.clicked.disconnect(self.player.startLive)
        self.player.btn_play.clicked.connect(self.play)

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
        self.player.layout().insertWidget(2, self.fixed_wave_form)

        self.layout().insertWidget(0, Options(self))

    def recorder_stbate(self, state: int):
        if state == 1:  # start
            self.player.setDisabled(True)

        elif state == 2:  # resume
            ...

        elif state == 3:  # pause
            ...

        else:  # stop
            self.player.byteArray = self.recorder.byteArray
            self.player.setEnabled(True)

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
            # self.player.live.byteArray = b""
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
        audiowave = self.player.audiowave

        # ---

        duration = audiowave.duration
        print(duration)
        self.play_wave_form.liveWaveFormChannel1.syncIntervalAndSamplesPerPixelWithDuration(
            duration
        )
        # self.play_wave_form.liveWaveFormChannel2.syncIntervalAndSamplesPerPixelWithDuration(
        #     duration
        # )
        self.fixed_wave_form.setSeconds(duration)

        # ---

        self.player.startLive()


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

    w = LiveAudioWaveFormWindow()
    # w = QColorDialog()
    w.show()
    a.exec()
