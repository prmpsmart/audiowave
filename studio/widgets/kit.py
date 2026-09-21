"""Small themed widgets shared by every page: segmented control, slider row, toggle, swatch, icon button."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QColorDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from studio.theme import Theme, get_theme, icon


def set_property(widget: QWidget, name: str, value: object) -> None:
    """Set a dynamic property and make the stylesheet re-evaluate the widget."""
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()


def chip(text: str = "", accent: bool = False) -> QLabel:
    label = QLabel(text)
    label.setProperty("chip", "accent" if accent else "true")
    return label


def separator() -> QFrame:
    line = QFrame()
    line.setObjectName("separator")
    return line


class IconButton(QToolButton):
    """A round/flat button whose glyph follows the theme (``role`` names a Theme colour)."""

    def __init__(
        self,
        name: str,
        *,
        kind: str = "round",
        size: int = 42,
        icon_size: int = 18,
        role: str = "text",
        checked_role: str | None = None,
        checkable: bool = False,
        tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._name, self._role, self._checked_role, self._icon_size = name, role, checked_role, icon_size
        self.setProperty("kind", kind)
        self.setFixedSize(size, size)
        self.setIconSize(QSize(icon_size, icon_size))
        self.setCheckable(checkable)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        self.toggled.connect(lambda _: self.refresh())
        self.refresh()

    def set_icon_name(self, name: str) -> None:
        self._name = name
        self.refresh()

    def refresh(self, theme: Theme | None = None) -> None:
        theme = theme or get_theme()
        role = self._checked_role if (self.isChecked() and self._checked_role) else self._role
        if not self.isEnabled():
            color = theme.dim
        else:
            color = getattr(theme, role)
        self.setIcon(icon(self._name, color, self._icon_size))

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type().name == "EnabledChange":
            self.refresh()


class Segmented(QFrame):
    """Mutually exclusive choices, like a tab strip."""

    currentChanged = Signal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, label in options:
            button = QPushButton(label)
            button.setProperty("segment", True)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self._group.addButton(button)
            self._buttons[key] = button
            layout.addWidget(button)
            button.clicked.connect(lambda _=False, k=key: self.currentChanged.emit(k))
        next(iter(self._buttons.values())).setChecked(True)

    @property
    def current(self) -> str:
        return next(k for k, b in self._buttons.items() if b.isChecked())

    def set_current(self, key: str, emit: bool = False) -> None:
        self._buttons[key].setChecked(True)
        if emit:
            self.currentChanged.emit(key)

    def set_enabled_keys(self, enabled: set[str]) -> None:
        for key, button in self._buttons.items():
            button.setEnabled(key in enabled)


class Toggle(QAbstractButton):
    """An on/off switch."""

    def __init__(self, checked: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setFixedSize(30, 17)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self, _: QPaintEvent) -> None:
        t = get_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(t.accent if self.isChecked() else t.line2))
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 8.5, 8.5)
        knob = 13
        x = self.width() - knob - 2 if self.isChecked() else 2
        p.setBrush(QColor(t.on_accent if self.isChecked() else t.muted))
        p.drawEllipse(QRectF(x, 2, knob, knob))
        p.end()


class LabeledSlider(QWidget):
    """``label  ----o----  value`` with float range and a value formatter."""

    valueChanged = Signal(float)

    def __init__(
        self,
        label: str,
        minimum: float,
        maximum: float,
        step: float = 1.0,
        fmt: Callable[[float], str] = lambda v: f"{v:g}",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._min, self._step, self._fmt = minimum, step, fmt
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self._label = QLabel(label)
        self._label.setObjectName("muted")
        self._label.setFixedWidth(74)
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, round((maximum - minimum) / step))
        self._value = QLabel()
        self._value.setObjectName("value")
        self._value.setFixedWidth(46)
        self._value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        for w, stretch in ((self._label, 0), (self._slider, 1), (self._value, 0)):
            layout.addWidget(w, stretch)
        self._slider.valueChanged.connect(self._on_slider)
        self._show(self.value())

    def value(self) -> float:
        return self._min + self._slider.value() * self._step

    def set_value(self, value: float) -> None:
        """Set without emitting ``valueChanged`` (used when the model changes)."""
        self._slider.blockSignals(True)
        self._slider.setValue(round((value - self._min) / self._step))
        self._slider.blockSignals(False)
        self._show(self.value())

    def _on_slider(self, _: int) -> None:
        self._show(self.value())
        self.valueChanged.emit(self.value())

    def _show(self, value: float) -> None:
        self._value.setText(self._fmt(value))


class ColorSwatch(QPushButton):
    """A colour chip with its name and hex value; clicking opens a colour dialog."""

    colorChanged = Signal(str)

    def __init__(self, label: str, color: str = "#000000", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._label, self._color = label, color
        self.setProperty("ghost", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(32)
        self.clicked.connect(self._pick)

    @property
    def color(self) -> str:
        return self._color

    def set_color(self, color: str) -> None:
        if color != self._color:
            self._color = color
            self.update()

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self._color), self, self._label)
        if chosen.isValid() and chosen.name() != self._color:
            self._color = chosen.name()
            self.update()
            self.colorChanged.emit(self._color)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        t = get_theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        chip_rect = QRectF(8, (self.height() - 16) / 2, 16, 16)
        p.setPen(QColor(255, 255, 255, 36) if t.is_dark else QColor(0, 0, 0, 40))
        p.setBrush(QColor(self._color))
        p.drawRoundedRect(chip_rect, 5, 5)
        p.setPen(QColor(t.muted))
        p.drawText(QRectF(32, 0, self.width() - 32, self.height()), int(Qt.AlignmentFlag.AlignVCenter), self._label)
        p.setPen(QColor(t.dim))
        p.drawText(QRectF(0, 0, self.width() - 8, self.height()), int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight), self._color.upper())
        p.end()


class Section(QWidget):
    """An inspector group: small uppercase title over a stack of rows."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(9)
        outer.addWidget(separator())
        header = QHBoxLayout()
        self._title = QLabel(title.upper())
        self._title.setObjectName("eyebrow")
        header.addWidget(self._title)
        header.addStretch()
        self.header = header
        outer.addLayout(header)
        self.body = QVBoxLayout()
        self.body.setSpacing(9)
        outer.addLayout(self.body)

    def add(self, widget: QWidget) -> None:
        self.body.addWidget(widget)
