"""Builds the application stylesheet from a Theme and the loaded fonts."""

from __future__ import annotations

from .fonts import Fonts
from .tokens import Theme


def build_stylesheet(t: Theme, f: Fonts) -> str:
    return f"""
* {{ font-family: "{f.sans}"; font-size: 13px; color: {t.text}; }}
QMainWindow, QWidget#root, QStackedWidget, QDialog {{ background: {t.bg}; }}
QWidget {{ background: transparent; }}
QToolTip {{ background: {t.surface2}; color: {t.text}; border: 1px solid {t.line2}; padding: 4px 8px; }}

/* surfaces */
QFrame#card {{ background: {t.surface}; border: 1px solid {t.line}; border-radius: 12px; }}
QFrame#well {{ background: {t.bg}; border: 1px solid {t.line}; border-radius: 10px; }}
QFrame#inspector {{ background: {t.surface}; border-left: 1px solid {t.line}; }}
QFrame#topbar {{ background: {t.surface}; border-bottom: 1px solid {t.line}; }}
QFrame#take {{ background: {t.surface}; border: 1px solid {t.line}; border-radius: 10px; }}
QFrame#take[current="true"] {{ background: {t.surface2}; border: 1px solid {t.accent}; }}
QFrame#take[new="true"] {{ border: 1px dashed {t.line2}; background: transparent; }}
QFrame#tile {{ background: {t.surface}; border: 1px solid {t.line}; border-radius: 12px; }}
QFrame#tile[selected="true"] {{ border: 1px solid {t.accent}; }}
QFrame#separator {{ background: {t.line}; max-height: 1px; min-height: 1px; border: none; }}

/* type */
QLabel#brand {{ font-family: "{f.serif}"; font-size: 24px; }}
QLabel#h1 {{ font-family: "{f.serif}"; font-size: 34px; }}
QLabel#h2 {{ font-family: "{f.serif}"; font-size: 20px; }}
QLabel#h3 {{ font-family: "{f.serif}"; font-size: 19px; }}
QLabel#eyebrow {{ color: {t.dim}; font-size: 10.5px; font-weight: 600; letter-spacing: 1px; }}
QLabel#muted {{ color: {t.muted}; font-size: 12px; }}
QLabel#dim {{ color: {t.dim}; font-size: 11px; }}
QLabel#mono {{ font-family: "{f.mono}"; }}
QLabel#bigtime {{ font-family: "{f.mono}"; font-size: 44px; font-weight: 300; }}
QLabel#bigtime_frac {{ font-family: "{f.mono}"; font-size: 30px; font-weight: 300; color: {t.dim}; }}
QLabel#subtime {{ font-family: "{f.mono}"; font-size: 11px; color: {t.dim}; }}
QLabel#value {{ font-family: "{f.mono}"; font-size: 11px; }}
QLabel[chip="true"] {{ font-family: "{f.mono}"; font-size: 11px; color: {t.muted}; border: 1px solid {t.line}; border-radius: 12px; padding: 3px 10px; }}
QLabel[chip="accent"] {{ font-family: "{f.mono}"; font-size: 11px; color: {t.accent}; border: 1px solid {t.line}; border-radius: 12px; padding: 3px 10px; }}
QLabel[tag="true"] {{ font-family: "{f.mono}"; font-size: 9px; font-weight: 500; letter-spacing: 1px; color: {t.on_accent}; background: {t.accent}; border-radius: 3px; padding: 2px 5px; }}
QLabel[state="ok"] {{ color: {t.teal}; background: {t.surface2}; border: 1px solid {t.teal}; border-radius: 15px; padding: 6px 14px; font-weight: 600; }}
QLabel[state="idle"] {{ color: {t.muted}; background: {t.surface2}; border: 1px solid {t.line2}; border-radius: 15px; padding: 6px 14px; font-weight: 600; }}
QLabel[state="error"] {{ color: {t.red}; background: {t.surface2}; border: 1px solid {t.red}; border-radius: 15px; padding: 6px 14px; font-weight: 600; }}

/* buttons */
QPushButton {{ background: {t.surface2}; border: 1px solid {t.line2}; border-radius: 7px; padding: 6px 12px; font-weight: 600; }}
QPushButton:hover {{ border-color: {t.muted}; }}
QPushButton:pressed {{ background: {t.line}; }}
QPushButton:disabled {{ color: {t.dim}; border-color: {t.line}; }}
QPushButton[primary="true"] {{ background: {t.accent}; border-color: {t.accent}; color: {t.on_accent}; }}
QPushButton[primary="true"]:disabled {{ background: {t.line2}; border-color: {t.line2}; color: {t.dim}; }}
QPushButton[ghost="true"] {{ background: transparent; }}
QPushButton[link="true"] {{ background: transparent; border: none; color: {t.accent}; padding: 0; }}
QPushButton[segment="true"] {{ background: transparent; border: none; border-radius: 6px; color: {t.muted}; padding: 5px 12px; }}
QPushButton[segment="true"]:checked {{ background: {t.surface2}; color: {t.text}; border: 1px solid {t.line2}; }}
QFrame#segmented {{ background: {t.bg}; border: 1px solid {t.line}; border-radius: 9px; }}
QToolButton {{ background: {t.surface2}; border: 1px solid {t.line2}; border-radius: 21px; }}
QToolButton:hover {{ border-color: {t.muted}; }}
QToolButton:disabled {{ border-color: {t.line}; }}
QToolButton[kind="play"] {{ background: {t.accent}; border: 1px solid {t.accent}; border-radius: 31px; }}
QToolButton[kind="small"] {{ border-radius: 17px; }}
QToolButton[kind="flat"] {{ background: transparent; border: none; border-radius: 7px; }}
QToolButton[kind="flat"]:hover {{ background: {t.surface2}; }}
QToolButton[kind="record"] {{ border-color: {t.red}; }}
QToolButton[kind="toggle"]:checked {{ background: {t.surface2}; border-color: {t.teal}; }}
QToolButton[kind="ms"] {{ border-radius: 4px; border: 1px solid {t.line2}; font-family: "{f.mono}"; font-size: 9px; padding: 1px 0; }}
QToolButton[kind="ms"]:checked {{ background: {t.accent}; color: {t.on_accent}; border-color: {t.accent}; }}
QToolButton[kind="pill"] {{ border-radius: 17px; font-family: "{f.mono}"; font-size: 11.5px; padding: 0 12px; }}

/* inputs */
QLineEdit, QSpinBox, QDoubleSpinBox {{ background: {t.bg}; border: 1px solid {t.line2}; border-radius: 7px; padding: 6px 10px; font-family: "{f.mono}"; selection-background-color: {t.accent}; selection-color: {t.on_accent}; }}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border-color: {t.accent}; }}
QLineEdit:disabled, QSpinBox:disabled {{ color: {t.dim}; }}
QComboBox {{ background: {t.surface2}; border: 1px solid {t.line2}; border-radius: 7px; padding: 5px 10px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {t.surface2}; border: 1px solid {t.line2}; selection-background-color: {t.line}; outline: none; }}
QSlider::groove:horizontal {{ height: 4px; background: {t.line2}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.accent}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {t.text}; width: 12px; height: 12px; margin: -4px 0; border-radius: 6px; }}
QSlider::handle:horizontal:disabled {{ background: {t.dim}; }}
QSlider::sub-page:horizontal:disabled {{ background: {t.line2}; }}

/* menus, tables, scrollbars */
QMenu {{ background: {t.surface2}; border: 1px solid {t.line2}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 5px; }}
QMenu::item:selected {{ background: {t.line}; }}
QTableView {{ background: transparent; border: none; gridline-color: {t.line}; font-family: "{f.mono}"; font-size: 11.5px; selection-background-color: transparent; outline: none; }}
QTableView::item {{ border-top: 1px solid {t.line}; padding: 4px 6px; color: {t.muted}; }}
QHeaderView::section {{ background: transparent; border: none; color: {t.dim}; font-size: 10px; padding: 4px 6px; text-align: left; }}
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t.line2}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {t.line2}; border-radius: 4px; min-width: 30px; }}
"""
