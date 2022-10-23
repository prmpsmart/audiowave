from mimi_wave import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *


class QtMimiWaveApp(MimiWaveApp, QApplication):
    def __init__(self, windowClass: MimiWaveWidget):
        QApplication.__init__(self)
        MimiWaveApp.__init__(self, windowClass)

    def start(self):
        self.window.show()
        exec = getattr(self, "exec", None)
        exec = exec or getattr(self, "exec_")
        exec()

    def closing(self):
        self.quit()


class QtMimiWaveWidgetCommon(QWidget):
    klass = None

    def __init__(self):
        QWidget.__init__(self, f=Qt.WindowStaysOnTopHint)

        self.setMinimumWidth(250)
        self.setMinimumWidth(250)

        self.setup()

    def GEOMETRY(self, geo):
        self.setGeometry(*geo)

    def INFO(self, title, text):
        QMessageBox.information(self, title, text)

    def TITLE(self, title):
        self.setWindowTitle(title)

    def CONNECT(self, widget: QWidget, func):
        widget.clicked.connect(func)

    def SET_TEXT(self, widget: QWidget, text):
        widget.setText(text)

    def GET_TEXT(self, widget: QWidget) -> str:
        return widget.text()

    def GET_INT(self, widget: QWidget) -> int:
        return widget.value()

    def DISABLE(self, widget: QWidget):
        widget.setEnabled(0)

    def ENABLE(self, widget: QWidget):
        widget.setEnabled(1)

    def setup(self):
        self._frames_details = QLabel()
        self._play_recording = QPushButton()
        self._server_port = QSpinBox()
        self._server_port.setRange(6000, 9000)
        self._server_port.setToolTip("Server Port")

    def closeEvent(self, event: QCloseEvent) -> None:
        self.klass.closing(self)
        return super().closeEvent(event)
