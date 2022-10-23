from .qt_app import *


class QtMimiWaveSender(QtMimiWaveWidgetCommon, MimiWaveSender):
    klass = MimiWaveSender

    def __init__(self, app: QtMimiWaveApp, title="Wave Sender"):
        MimiWaveSender.__init__(self, app=app, title=title, geo=(50, 50, 1, 1))
        QtMimiWaveWidgetCommon.__init__(self)

    def setup(self):
        QtMimiWaveWidgetCommon.setup(self)

        vlayout = QVBoxLayout(self)

        recording_box = QGroupBox("Recording")
        vlayout.addWidget(recording_box)

        recording_layout = QGridLayout(recording_box)

        self._record = QPushButton()
        recording_layout.addWidget(self._record, 0, 0)

        recording_layout.addWidget(self._frames_details, 0, 1)

        self._stop_recording = QPushButton()
        self._stop_recording.setEnabled(0)
        recording_layout.addWidget(self._stop_recording, 1, 0)

        recording_layout.addWidget(self._play_recording, 1, 1)

        transfer_box = QGroupBox("Transfer")
        vlayout.addWidget(transfer_box)

        transfer_layout = QGridLayout(transfer_box)

        self._start_server = QPushButton()
        transfer_layout.addWidget(self._start_server, 0, 0)

        transfer_layout.addWidget(self._server_port, 0, 1)

        self._stop_server = QPushButton()
        self._stop_server.setEnabled(0)
        transfer_layout.addWidget(self._stop_server, 1, 0)

        self._send_recorded = QPushButton()
        self._send_recorded.setEnabled(0)
        transfer_layout.addWidget(self._send_recorded, 1, 1)

        MimiWaveSender.setup(self)


QtMimiWaveApp(QtMimiWaveSender)
