from .app import *


class MimiWaveReceiver(MimiWaveWidget):
    def __init__(self, *args, title="Wave Receiver", **kwargs):
        super().__init__(title=title, *args, **kwargs)

        self.connected = False
        self.wave_player.start_stream()
        self.frames = self.wave_player.frames

        self._server_ip: MimiWidget = None
        self._connect: MimiWidget = None
        self._disconnect: MimiWidget = None

    def setup(self):
        super().setup()

        self.SET_TEXT(self._server_ip, "localhost")
        self.SET_TEXT(self._connect, "Connect")
        self.SET_TEXT(self._disconnect, "Disconnect")

        self.CONNECT(self._connect, self.connect_)
        self.CONNECT(self._disconnect, self.disconnect_)
        self.DISABLE(self._disconnect)

    def get_ip_port(self):
        ip = self.GET_TEXT(self._server_ip)
        port = self.get_port()
        if not port:
            return

        if not ip:
            self.INFO("Invalid IP", "Enter a valid IP Address.")
            return

        return ip, port

    def connect_(self):
        ip_port = self.get_ip_port()
        if ip_port:
            ip, port = ip_port

            try:
                self.sock = MimiSocket(ip=ip, port=port)
                self.connected = True
                THREAD(self._start_receiving)
                self.DISABLE(self._connect)
                self.ENABLE(self._disconnect)
                self.DISABLE(self._server_ip)
                self.DISABLE(self._server_port)

            except:
                ...

    def _start_receiving(self):
        chunks = b""
        available = False

        while self.connected:
            chunk = b""
            try:
                chunk = self.sock.recv(4096)
            except Exception as e:
                break

            if not chunk:
                break

            chunks += chunk
            datas = []
            if self.DELIM in chunks:
                datas = chunks.split(self.DELIM)

            if datas:
                if chunks.endswith(self.DELIM):
                    chunks = b""
                else:
                    chunks = datas[-1]
                    datas = datas[:-1]

                for data in datas:
                    if data:
                        self.frames.add(data)
                        self.update_frames_details(self.frames)

                        if not available:
                            available = True
                            self.ENABLE(self._play_recording)
        self.disconnect_()

    def play_recording(self):
        super().play_recording(1)

    def disconnect_(self):
        self.connected = False
        self.ENABLE(self._connect)
        self.DISABLE(self._disconnect)
        self.ENABLE(self._server_ip)
        self.ENABLE(self._server_port)

    def closing(self) -> None:
        self.disconnect_()
        return super().closing()
