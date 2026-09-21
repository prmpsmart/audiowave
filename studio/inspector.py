"""Inspector: the appearance controls, grouped and shown only when they apply to the chosen style."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from audiowave import Appearance, Gravity
from audiowave.widgets import get_painter

from .models import AppearanceModel, PresetStore, Target
from .theme import get_theme
from .widgets import ColorSwatch, LabeledSlider, Section, Segmented, Toggle
from .widgets.style_picker import StylePicker

INSPECTOR_STYLES = ["bars", "capsule", "hair", "env", "line", "dots", "stairs", "rms"]
_COLOR_FIELDS = [
    ("played", "Played"),
    ("unplayed", "Unplayed"),
    ("playhead", "Playhead"),
    ("background", "Background"),
    ("loop", "Loop"),
    ("grid", "Grid"),
]
_GRAVITY = [("average", "Average"), ("min_max", "Min·Max"), ("min", "Min"), ("max", "Max")]


class Inspector(QFrame):
    """Edits an :class:`AppearanceModel`. Holds no state of its own: every control is refreshed from the model."""

    openStyleLab = Signal()

    def __init__(
        self, model: AppearanceModel, presets: PresetStore, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("inspector")
        self.setFixedWidth(340)
        self._model, self._presets = model, presets
        self._building = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)
        body = QWidget()
        scroll.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(18, 16, 18, 16)
        col.setSpacing(13)

        col.addLayout(self._header())
        col.addWidget(self._style_section())
        col.addWidget(self._target_row())
        self._gravity_section = self._make_gravity()
        col.addWidget(self._gravity_section)
        self._shape_section = self._make_shape()
        col.addWidget(self._shape_section)
        col.addWidget(self._make_colours())
        col.addWidget(self._make_display())
        col.addStretch()

        model.changed.connect(self.refresh)
        self.refresh()

    # -- construction ---------------------------------------------------------------------------

    def _header(self) -> QHBoxLayout:
        row = QHBoxLayout()
        title = QLabel("Appearance")
        title.setObjectName("h3")
        row.addWidget(title)
        row.addStretch()
        self._presets_button = QPushButton("Presets")
        self._presets_button.setProperty("link", True)
        self._presets_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._presets_button.clicked.connect(self._show_presets)
        row.addWidget(self._presets_button)
        return row

    def _style_section(self) -> QWidget:
        section = QWidget()
        col = QVBoxLayout(section)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(8)
        head = QHBoxLayout()
        eyebrow = QLabel("STYLE")
        eyebrow.setObjectName("eyebrow")
        link = QPushButton("All styles in Style Lab →")
        link.setProperty("link", True)
        link.setCursor(Qt.CursorShape.PointingHandCursor)
        link.clicked.connect(self.openStyleLab)
        head.addWidget(eyebrow)
        head.addStretch()
        head.addWidget(link)
        col.addLayout(head)
        self._picker = StylePicker(INSPECTOR_STYLES)
        self._picker.styleChosen.connect(lambda name: self._model.update(style=name))
        col.addWidget(self._picker)
        return section

    def _target_row(self) -> QWidget:
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(5)
        self._target = Segmented([("linked", "Linked"), ("left", "L"), ("right", "R")])
        self._target.currentChanged.connect(lambda key: self._model.set_target(Target(key)))
        self._mixed = QLabel("Channels differ: edits apply to both")
        self._mixed.setObjectName("dim")
        col.addWidget(self._target)
        col.addWidget(self._mixed)
        return box

    def _make_gravity(self) -> Section:
        section = Section("Gravity")
        self._gravity = Segmented(_GRAVITY)
        self._gravity.currentChanged.connect(lambda key: self._model.update(gravity=Gravity(key)))
        section.add(self._gravity)
        return section

    def _slider(
        self, section: Section, label: str, field: str, lo: float, hi: float, step: float, fmt
    ) -> LabeledSlider:
        slider = LabeledSlider(label, lo, hi, step, fmt)
        slider.valueChanged.connect(lambda v, f=field: self._model.update(**{f: v}))
        section.add(slider)
        return slider

    def _make_shape(self) -> Section:
        section = Section("Shape")
        px = lambda v: f"{v:g} px"  # noqa: E731
        self._bar_sliders = [
            self._slider(section, "Width", "bar_width", 1, 12, 0.5, px),
            self._slider(section, "Spacing", "bar_spacing", 0, 10, 0.5, px),
            self._slider(section, "Radius", "radius", 0, 6, 0.5, px),
        ]
        self._scale = self._slider(
            section, "Scale", "scale", 0.2, 1.0, 0.02, lambda v: f"{v * 100:.0f} %"
        )
        self._idle = self._slider(section, "Idle height", "idle_height", 0, 8, 0.5, px)
        return section

    def _make_colours(self) -> Section:
        section = Section("Colour")
        grid = QWidget()
        rows = QVBoxLayout(grid)
        rows.setContentsMargins(0, 0, 0, 0)
        rows.setSpacing(7)
        self._swatches: dict[str, ColorSwatch] = {}
        for i in range(0, len(_COLOR_FIELDS), 2):
            line = QHBoxLayout()
            line.setSpacing(7)
            for key, label in _COLOR_FIELDS[i : i + 2]:
                swatch = ColorSwatch(label)
                swatch.colorChanged.connect(
                    lambda color, k=key: self._model.update_palette(**{k: color})
                )
                self._swatches[key] = swatch
                line.addWidget(swatch)
            rows.addLayout(line)
        section.add(grid)
        self._seeker = self._slider(
            section, "Seeker", "playhead_radius", 0, 12, 1, lambda v: f"{v:g} px"
        )
        return section

    def _make_display(self) -> Section:
        section = Section("Display")
        self._toggles: dict[str, Toggle] = {}
        for key, label in (
            ("show_grid", "Grid"),
            ("show_midline", "Midline"),
            ("auto_gain", "Auto gain"),
        ):
            row = QHBoxLayout()
            name = QLabel(label)
            name.setObjectName("muted")
            toggle = Toggle()
            row.addWidget(name)
            row.addStretch()
            row.addWidget(toggle)
            container = QWidget()
            container.setLayout(row)
            row.setContentsMargins(0, 0, 0, 0)
            section.add(container)
            self._toggles[key] = toggle
            toggle.toggled.connect(lambda on, k=key: self._on_toggle(k, on))
        return section

    def _on_toggle(self, key: str, on: bool) -> None:
        if self._building:
            return
        if key == "auto_gain":
            self._model.set_auto_gain(on)
        else:
            self._model.update(**{key: on})

    # -- model -> widgets -----------------------------------------------------------------------

    def refresh(self) -> None:
        a: Appearance = self._model.editing
        painter = get_painter(a.style)
        self._building = True
        self._picker.set_palette(a.palette)
        self._picker.set_current(a.style)
        self._target.set_current(self._model.target.value)
        self._mixed.setVisible(self._model.mixed and self._model.target is Target.LINKED)
        self._gravity.set_current(a.gravity.value)
        self._gravity_section.setVisible(painter.uses_gravity)
        for slider, value in zip(
            self._bar_sliders, (a.bar_width, a.bar_spacing, a.radius), strict=True
        ):
            slider.set_value(value)
            slider.setVisible(painter.uses_bar_shape)
        self._scale.set_value(a.scale)
        self._idle.set_value(a.idle_height)
        for key, swatch in self._swatches.items():
            swatch.set_color(getattr(a.palette, key))
        self._seeker.set_value(a.playhead_radius)
        self._toggles["show_grid"].setChecked(a.show_grid)
        self._toggles["show_midline"].setChecked(a.show_midline)
        self._toggles["auto_gain"].setChecked(self._model.auto_gain)
        self._building = False

    # -- presets --------------------------------------------------------------------------------

    def _show_presets(self) -> None:
        menu = QMenu(self)
        menu.addAction("Save current as…", self._save_preset)
        names = self._presets.names()
        if names:
            menu.addSeparator()
            for name in names:
                sub = menu.addMenu(name)
                sub.addAction("Apply", lambda n=name: self._apply_preset(n))
                sub.addAction("Delete", lambda n=name: self._presets.delete(n))
        menu.addSeparator()
        menu.addAction("Reset to default", self._reset)
        menu.exec(self._presets_button.mapToGlobal(self._presets_button.rect().bottomLeft()))

    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name")
        if ok and name.strip():
            self._presets.save(name.strip(), self._model.editing)

    def _apply_preset(self, name: str) -> None:
        if (appearance := self._presets.load(name)) is not None:
            self._model.replace_all(appearance)

    def _reset(self) -> None:
        self._model.replace_all(Appearance(palette=get_theme().waveform))
