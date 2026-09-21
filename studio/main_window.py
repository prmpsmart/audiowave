"""MainWindow: the shell that hosts the pages, the inspector and the top bar."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtMultimedia import QMediaDevices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from audiowave.audio import PlayerState, RecorderState, input_devices, output_devices
from studio.inspector import Inspector
from studio.models import Take
from studio.pages.lab_page import LabPage
from studio.pages.player_page import PlayerPage
from studio.pages.record_page import RecordPage
from studio.pages.stream_page import StreamPage
from studio.session import Session
from studio.theme import (
    DARK,
    LIGHT,
    Fonts,
    Theme,
    build_stylesheet,
    get_theme,
    set_theme,
)
from studio.widgets import IconButton, Segmented, set_property

PAGES = ["record", "player", "stream", "styles"]
MESSAGE_MS = 5000


class MainWindow(QMainWindow):
    def __init__(self, session: Session, fonts: Fonts, theme: Theme = DARK) -> None:
        super().__init__()
        self._s, self._fonts = session, fonts
        self.setWindowTitle("AudioWave")
        self.resize(1440, 900)
        self.setMinimumSize(1100, 720)
        self.setAcceptDrops(True)

        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        col = QVBoxLayout(root)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        col.addWidget(self._top_bar())

        body = QHBoxLayout()
        body.setSpacing(0)
        self.stack = QStackedWidget()
        self.record_page = RecordPage(session)
        self.player_page = PlayerPage(session)
        self.stream_page = StreamPage(session)
        self.lab_page = LabPage(session)
        for page in (
            self.record_page,
            self.player_page,
            self.stream_page,
            self.lab_page,
        ):
            self.stack.addWidget(page)
        self.inspector = Inspector(session.appearance, session.presets)
        body.addWidget(self.stack, 1)
        body.addWidget(self.inspector)
        col.addLayout(body, 1)

        self._wire()
        self._shortcuts()
        self.apply_theme(theme)
        self.show_page("player")
        self._on_take(session.takes.current)

    # -- construction ---------------------------------------------------------------------------

    def _top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("topbar")
        bar.setFixedHeight(52)
        row = QHBoxLayout(bar)
        row.setContentsMargins(18, 5, 14, 5)
        row.setSpacing(18)

        brand = QLabel(f'Audio<i style="color:{get_theme().accent}">Wave</i>')
        brand.setObjectName("brand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        self._brand = brand
        self._file = QLabel()
        self._file.setObjectName("muted")
        self.message = QLabel()
        self.message.setObjectName("muted")

        self.tabs = Segmented(
            [
                ("record", "Record", "rec"),
                ("player", "Player", "play"),
                ("stream", "Stream", "net"),
                ("styles", "Styles", "lab"),
            ]
        )
        self.tabs.setFixedWidth(420)

        self.input_combo, self.output_combo = QComboBox(), QComboBox()
        for combo in (self.input_combo, self.output_combo):
            combo.setMinimumWidth(180)
            combo.setMaximumWidth(230)
        self._devices = QMediaDevices(self)  # keeps the lists current when a device is plugged in
        self._devices.audioInputsChanged.connect(self._refresh_devices)
        self._devices.audioOutputsChanged.connect(self._refresh_devices)
        self._refresh_devices()

        self.theme_button = IconButton(
            "sun",
            kind="flat",
            size=32,
            icon_size=17,
            role="muted",
            tooltip="Toggle light / dark theme",
        )

        row.addWidget(brand)
        row.addWidget(self._file)
        row.addWidget(self.message)
        row.addStretch(1)
        row.addWidget(self.tabs)
        row.addStretch(1)
        for label, combo in (("In", self.input_combo), ("Out", self.output_combo)):
            caption = QLabel(label)
            caption.setObjectName("dim")
            row.addWidget(caption)
            row.addWidget(combo)
        row.addWidget(self.theme_button)
        return bar

    def _wire(self) -> None:
        s = self._s
        self.tabs.currentChanged.connect(self.show_page)
        self.theme_button.clicked.connect(self.toggle_theme)
        self.input_combo.currentIndexChanged.connect(self._on_input_chosen)
        self.output_combo.currentIndexChanged.connect(self._on_output_chosen)

        self.player_page.recordRequested.connect(lambda: self.show_page("record"))
        self.record_page.recorded.connect(lambda _take: self.show_page("player"))
        self.stream_page.playRequested.connect(self._play_take)
        self.inspector.openStyleLab.connect(lambda: self.show_page("styles"))

        s.message.connect(self.show_message)
        s.takes.currentChanged.connect(self._on_take)
        s.takes.renamed.connect(lambda _t: self._on_take(s.takes.current))

    def _shortcuts(self) -> None:
        def bind(key: str, handler) -> None:
            QShortcut(QKeySequence(key), self, activated=handler)

        bind("Space", lambda: self._on_page("player", self._s.player.toggle))
        bind(
            "M",
            lambda: self._on_page("player", lambda: self._s.add_marker(self._s.player.position)),
        )
        bind(
            "L",
            lambda: self._on_page(
                "player", lambda: self._s.set_loop_enabled(not self._s.loop_enabled)
            ),
        )
        bind("R", lambda: self._on_page("record", self.record_page.toggle_recording))
        bind("Ctrl+O", lambda: self._on_page("player", self.player_page.open_dialog))

    def _on_page(self, page: str, action) -> None:
        if PAGES[self.stack.currentIndex()] == page:
            action()

    # -- navigation -----------------------------------------------------------------------------

    def show_page(self, key: str) -> None:
        self.stack.setCurrentIndex(PAGES.index(key))
        self.tabs.set_current(key)
        self.inspector.setVisible(key != "styles")

    def _play_take(self, take: Take) -> None:
        self.show_page("player")
        self._s.player.play()

    # -- feedback -------------------------------------------------------------------------------

    def show_message(self, text: str, is_error: bool = False) -> None:
        self.message.setText(text)
        set_property(self.message, "error", is_error)
        self.message.setStyleSheet(f"color: {get_theme().red if is_error else get_theme().teal};")
        QTimer.singleShot(
            MESSAGE_MS,
            lambda t=text: self.message.setText("") if self.message.text() == t else None,
        )

    def _on_take(self, take: Take | None) -> None:
        if take is None:
            self._file.setText("")
            return
        saved = "saved" if take.path else "unsaved"
        self._file.setText(f"{take.name}{'.wav' if take.path else ''}  ·  {saved}")

    # -- devices --------------------------------------------------------------------------------

    def _refresh_devices(self) -> None:
        self._input_list, self._output_list = input_devices(), output_devices()
        for combo, devices in (
            (self.input_combo, self._input_list),
            (self.output_combo, self._output_list),
        ):
            combo.blockSignals(True)
            combo.clear()
            for device in devices:
                combo.addItem(device.name)
            default = next((i for i, d in enumerate(devices) if d.is_default), 0)
            combo.setCurrentIndex(default if devices else -1)
            combo.blockSignals(False)
        self._on_input_chosen()
        self._on_output_chosen()

    def _on_input_chosen(self, *_: object) -> None:
        i = self.input_combo.currentIndex()
        self._s.set_input_device(self._input_list[i] if 0 <= i < len(self._input_list) else None)

    def _on_output_chosen(self, *_: object) -> None:
        i = self.output_combo.currentIndex()
        device = self._output_list[i] if 0 <= i < len(self._output_list) else None
        self._s.set_output_device(device if device is not None and not device.is_default else None)

    # -- theme ----------------------------------------------------------------------------------

    def toggle_theme(self) -> None:
        self.apply_theme(LIGHT if get_theme().is_dark else DARK)

    def apply_theme(self, theme: Theme) -> None:
        set_theme(theme)
        QApplication.instance().setStyleSheet(build_stylesheet(theme, self._fonts))  # type: ignore[union-attr]
        self._s.appearance.apply_palette(theme.waveform)
        self._brand.setText(f'Audio<i style="color:{theme.accent}">Wave</i>')
        self.theme_button.set_icon_name("sun" if theme.is_dark else "moon")
        for button in self.findChildren(IconButton):
            button.refresh(theme)
        self.tabs.refresh_icons()
        for page in (
            self.record_page,
            self.player_page,
            self.stream_page,
            self.lab_page,
        ):
            page.refresh_theme()
        self.inspector.refresh()

    # -- drag & drop ----------------------------------------------------------------------------

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if any(u.toLocalFile().lower().endswith(".wav") for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        for url in event.mimeData().urls():
            if url.toLocalFile().lower().endswith(".wav"):
                self._s.open_file(url.toLocalFile())
                self.show_page("player")

    def closeEvent(self, event) -> None:
        if self._s.recorder.state is not RecorderState.STOPPED:
            self._s.recorder.stop()
        self._s.player.stop()
        self.stream_page.sender.stop()
        self.stream_page.receiver.disconnect_from()
        super().closeEvent(event)


__all__ = ["PAGES", "MainWindow", "PlayerState"]
