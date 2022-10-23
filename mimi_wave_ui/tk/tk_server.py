from socket import socket, timeout
from typing import List
from .tk_app import *


class TkMimiWaveSender(TkMimiWaveWidgetCommon, MimiWaveSender):
    klass = MimiWaveSender

    def __init__(self, app: TkMimiWaveApp, title="Wave Sender"):
        MimiWaveSender.__init__(self, app=app, title=title, geo=(250, 200, 50, 50))
        TkMimiWaveWidgetCommon.__init__(self, app)

    def setup(self):
        recording_box = LabelFrame(self, text="Recording")
        recording_box.place(relx=0.02, rely=0.05, relw=0.96, relh=0.43)

        transfer_box = LabelFrame(self, text="Transfer")
        transfer_box.place(relx=0.02, rely=0.5, relw=0.96, relh=0.43)

        TkMimiWaveWidgetCommon.setup(self, (recording_box, recording_box, transfer_box))

        self._record = Button(recording_box, relief="groove")
        self._record.place(relx=0.02, rely=0.05, relw=0.47, relh=0.42)

        self._stop_recording = Button(
            recording_box,
            relief="groove",
        )
        self._stop_recording.place(relx=0.02, rely=0.5, relw=0.47, relh=0.42)

        self._frames_details.place(relx=0.52, rely=0.05, relw=0.47, relh=0.42)
        self._play_recording.place(relx=0.52, rely=0.5, relw=0.47, relh=0.42)

        self._start_server = Button(
            transfer_box,
            relief="groove",
        )
        self._start_server.place(relx=0.02, rely=0.05, relw=0.47, relh=0.42)
        self._start_server.place()

        self._stop_server = Button(transfer_box, relief="groove")
        self._stop_server.place(relx=0.02, rely=0.5, relw=0.47, relh=0.42)
        self._stop_server["state"] = "disabled"

        self._server_port.place(relx=0.51, rely=0.05, relw=0.47, relh=0.40)

        self._send_recorded = Button(
            transfer_box,
            relief="groove",
        )
        self._send_recorded.place(relx=0.51, rely=0.5, relw=0.47, relh=0.42)

        MimiWaveSender.setup(self)


TkMimiWaveApp(TkMimiWaveSender)
