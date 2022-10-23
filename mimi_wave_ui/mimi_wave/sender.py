from socket import socket, timeout
from typing import List
from .app import *


class MimiWaveSender(MimiWaveWidget):
    def __init__(self, *args, title="Wave Sender", **kwargs):
        super().__init__(title=title, *args, **kwargs)

        self.serving = False
        self.wave_recorder = AudioWaveRecorder(callback=self.recording)
        self.frames = self.wave_recorder.frames
        self.clients: List[socket] = []

        self._record: MimiWidget = None
        self._stop_recording: MimiWidget = None
        self._start_server: MimiWidget = None
        self._stop_server: MimiWidget = None
        self._send_recorded: MimiWidget = None

    def setup(self):
        super().setup()

        self.SET_TEXT(self._record, "Record")
        self.CONNECT(self._record, self.record)

        self.SET_TEXT(self._stop_recording, "Stop Recording")
        self.CONNECT(self._stop_recording, self.stop_recording)
        self.DISABLE(self._stop_recording)

        self.SET_TEXT(self._start_server, "Start Server")
        self.CONNECT(self._start_server, self.start_server)

        self.SET_TEXT(self._stop_server, "Stop Server")
        self.CONNECT(self._stop_server, self.stop_server)
        self.DISABLE(self._stop_server)

        self.SET_TEXT(self._send_recorded, "Send Recorded")
        self.CONNECT(self._send_recorded, self.send_recorded)
        self.DISABLE(self._send_recorded)

    def record(self):
        self.frames.clear()
        self.wave_recorder.resume()
        self.wave_recorder.record(block=0)
        self.DISABLE(self._record)
        self.DISABLE(self._send_recorded)

    def recording(
        self,
        state: AudioWaveState = None,
        error: AudioWaveError = None,
        frames: AudioWaveFrames = None,
        **kwargs
    ):
        self.update_frames_details(frames)
        if state:
            if state != AudioWaveState.Complete:
                self.ENABLE(self._stop_recording)
                self.DISABLE(self._play_recording)
                self.DISABLE(self._send_recorded)

            else:
                self.ENABLE(self._record)
                self.ENABLE(self._play_recording)
                self.DISABLE(self._stop_recording)

                if self.serving:
                    self.ENABLE(self._send_recorded)
                else:
                    self.DISABLE(self._send_recorded)
        elif error:
            self.wave_recorder.recreate_stream()
            print(error)

    def stop_recording(self):
        self.wave_recorder.pause()
        self.recording()

    def play_recording(self):
        super().play_recording(extra=self.wave_recorder._pause)

    def start_server(self):
        port = self.get_port()
        if port:
            if not self.sock:
                self.sock = MimiSocket(ip="", port=port, server=True)
                self.sock.listen(10)

            if not self.serving:
                self.serving = True
                THREAD(self.__start_server)

            self.DISABLE(self._start_server)
            self.DISABLE(self._server_port)
            self.ENABLE(self._stop_server)
            if self.frames:
                self.ENABLE(self._send_recorded)

        else:
            return

    def __start_server(self):
        while self.serving:
            try:
                client, address = self.sock.accept()
                self.clients.append(client)
            except timeout:
                ...
            except:
                self.stop_server()

    def stop_server(self):
        self.serving = False
        self.ENABLE(self._start_server)
        self.DISABLE(self._stop_server)
        self.DISABLE(self._send_recorded)

    def send_recorded(self):
        if self.frames:
            for frame in self.frames:
                clients = self.clients.copy()
                for client in clients:
                    try:
                        client.send(frame + self.DELIM)
                    except:
                        self.clients.remove(client)

            # self.frames.clear()

    def closing(self) -> None:
        self.wave_recorder.close()
        self.stop_server()
        return super().closing()
