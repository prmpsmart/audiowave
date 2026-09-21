"""EditBar: the editing actions for the current take (trim, cut, fades, normalise, silences, undo/redo)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QMenu, QPushButton, QWidget

from studio.theme import get_theme, icon

from .kit import IconButton

LOUDNESS_TARGETS = (
    ("−14 LUFS · streaming", -14.0),
    ("−16 LUFS · podcast", -16.0),
    ("−23 LUFS · broadcast (EBU R128)", -23.0),
)


class EditBar(QFrame):
    """Emits ``action(name, value)`` for the page to route; holds no editing logic itself.

    Buttons that need a selection (trim, cut, silence) are disabled until one exists, so the user
    sees why nothing would happen instead of getting an error afterwards.
    """

    action = Signal(str, object)  # name, optional float

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)

        self._needs_selection: list[IconButton] = []
        self._needs_clip: list[QWidget] = []
        for name, glyph, tip, needs_selection in (
            ("trim", "trim", "Trim to selection (Ctrl+T)", True),
            ("cut", "scissors", "Cut selection (Delete)", True),
            ("silence_selection", "mute", "Silence selection", True),
            ("fade_in", "fadein", "Fade in over the selection, or the first 0.5 s", False),
            ("fade_out", "fadeout", "Fade out over the selection, or the last 0.5 s", False),
        ):
            button = IconButton(glyph, kind="flat", size=32, icon_size=17, role="text", tooltip=tip)
            button.clicked.connect(lambda _=False, n=name: self.action.emit(n, None))
            row.addWidget(button)
            (self._needs_selection if needs_selection else self._needs_clip).append(button)

        self._normalize = self._menu_button("Normalize", "level", self._normalize_menu)
        self._silences = self._menu_button("Silences", "wave", self._silence_menu)
        row.addWidget(self._normalize)
        row.addWidget(self._silences)
        self._needs_clip += [self._normalize, self._silences]

        self.undo = IconButton("undo", kind="flat", size=32, icon_size=17, tooltip="Undo (Ctrl+Z)")
        self.redo = IconButton(
            "redo", kind="flat", size=32, icon_size=17, tooltip="Redo (Ctrl+Shift+Z)"
        )
        self.undo.clicked.connect(lambda: self.action.emit("undo", None))
        self.redo.clicked.connect(lambda: self.action.emit("redo", None))
        row.addSpacing(6)
        row.addWidget(self.undo)
        row.addWidget(self.redo)
        self.set_state(False, False, False, False, False)

    def _menu_button(self, text: str, glyph: str, build) -> QPushButton:
        button = QPushButton(text)
        button.setProperty("ghost", True)
        button.setIcon(icon(glyph, get_theme().text, 16))
        button.setMenu(build(button))
        button.setProperty("glyph", glyph)
        return button

    def _normalize_menu(self, parent: QWidget) -> QMenu:
        menu = QMenu(parent)
        menu.addAction("Peak to −1 dBFS", lambda: self.action.emit("normalize_peak", -1.0))
        menu.addSeparator()
        for label, target in LOUDNESS_TARGETS:
            menu.addAction(label, lambda t=target: self.action.emit("normalize_loudness", t))
        return menu

    def _silence_menu(self, parent: QWidget) -> QMenu:
        menu = QMenu(parent)
        menu.addAction("Find silences", lambda: self.action.emit("find_silences", None))
        menu.addAction("Remove found silences", lambda: self.action.emit("remove_silences", None))
        menu.addAction(
            "Trim silence at start and end", lambda: self.action.emit("trim_silence", None)
        )
        menu.addSeparator()
        menu.addAction("Clear highlights", lambda: self.action.emit("clear_silences", None))
        return menu

    def set_state(
        self, has_clip: bool, has_selection: bool, can_undo: bool, can_redo: bool, busy: bool
    ) -> None:
        for w in self._needs_selection:
            w.setEnabled(has_clip and has_selection and not busy)
        for w in self._needs_clip:
            w.setEnabled(has_clip and not busy)
        self.undo.setEnabled(can_undo and not busy)
        self.redo.setEnabled(can_redo and not busy)

    def refresh_icons(self) -> None:
        for button in self.findChildren(IconButton):
            button.refresh(get_theme())
        for button in self.findChildren(QPushButton):
            if glyph := button.property("glyph"):
                button.setIcon(icon(glyph, get_theme().text, 16))
