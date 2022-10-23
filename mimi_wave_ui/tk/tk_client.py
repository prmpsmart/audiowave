from .tk_app import *


class TkMimiWaveReceiver(TkMimiWaveWidgetCommon, MimiWaveReceiver):
    klass = MimiWaveReceiver

    def __init__(self, app: MimiWaveApp, title="Wave Receiver"):
        MimiWaveReceiver.__init__(self, app=app, title=title, geo=(250, 150, 1000, 50))
        TkMimiWaveWidgetCommon.__init__(self, app)

    def setup(self):
        TkMimiWaveWidgetCommon.setup(self)

        Label(self, text="Server IP", anchor="w").place(
            relx=0.02, rely=0.05, relw=0.3, relh=0.16
        )
        self._server_ip = Entry(self)
        self.SET_TEXT(self._server_ip, "localhost")
        self._server_ip.place(relx=0.34, rely=0.05, relw=0.62, relh=0.16)

        Label(self, text="Server Port", anchor="w").place(
            relx=0.02, rely=0.24, relw=0.3, relh=0.16
        )
        self._server_port.place(relx=0.34, rely=0.24, relw=0.62, relh=0.16)

        self._connect = Button(self, relief="groove")
        self._connect.place(relx=0.02, rely=0.45, relw=0.47, relh=0.2)

        self._disconnect = Button(self, relief="groove")
        self._disconnect.place(relx=0.51, rely=0.45, relw=0.47, relh=0.2)

        self._frames_details.place(relx=0.02, rely=0.70, relw=0.47, relh=0.2)

        self._play_recording.place(relx=0.51, rely=0.70, relw=0.47, relh=0.2)

        MimiWaveReceiver.setup(self)


TkMimiWaveApp(TkMimiWaveReceiver)
