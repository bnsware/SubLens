"""Colours, stylesheet and painted icons.

Neutral graphite with one accent: subtitle yellow - the colour of classic
film subtitles, which is what the app is about. No emoji anywhere; the few
icons are painted here so they look the same on every Windows install.
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QPointF, QRectF, QObject, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QPixmap, QIcon
from PySide6.QtWidgets import QComboBox, QStyledItemDelegate

BG = "#121314"
SURFACE = "#1a1b1d"
SURFACE_2 = "#222326"
SURFACE_3 = "#2b2c30"
BORDER = "#2e2f33"
TEXT = "#e9e7e3"
DIM = "#8f8d88"
FAINT = "#5c5b58"
ACCENT = "#f2c14e"          # subtitle yellow
ACCENT_HI = "#f7d27a"
ON_ACCENT = "#1b1606"
OK = "#5cbf7d"
WARN = "#e9a23b"
ERR = "#e5605a"

ENGINE_COLOR = {"google": "#6aa7f0", "deepl": "#3fb9d9", "openai": "#a9adb5",
                "claude": "#d9825f", "gemini": "#6cc49a"}

_SHEET = """
QWidget {{ color: {TEXT}; font-family: 'Segoe UI'; font-size: 10pt; }}
QMainWindow, QDialog, QWidget#page {{ background: {BG}; }}
QScrollArea {{ background: {BG}; border: none; }}
QFrame#topbar {{ background: {BG}; border-bottom: 1px solid {BORDER}; }}
QFrame#bottombar {{ background: {SURFACE}; border-top: 1px solid {BORDER}; }}
QLabel#brand {{ font: 600 12.5pt 'Segoe UI'; color: {TEXT}; }}
QLabel#state {{ font: 600 9pt 'Segoe UI'; }}
QLabel#section {{ color: {DIM}; font: 600 8.5pt 'Segoe UI'; letter-spacing: 0.6px;
    padding: 0 2px; }}
QLabel#rowlabel {{ color: {TEXT}; }}
QLabel#dim {{ color: {DIM}; }}
QLabel#hint {{ color: {DIM}; font-size: 9pt; }}
QLabel#key {{ color: {DIM}; background: {SURFACE_2}; border: 1px solid {BORDER};
    border-radius: 4px; padding: 0 5px; font: 600 8pt 'Segoe UI'; }}

QFrame#monitor {{ background: #08090a; border: 1px solid {BORDER}; border-radius: 6px; }}
QLabel#screen {{ color: {FAINT}; }}
QFrame#list {{ background: {SURFACE}; border: 1px solid {BORDER}; border-radius: 6px; }}
QFrame#divider {{ background: {BORDER}; max-height: 1px; min-height: 1px; border: none; }}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QPlainTextEdit {{
    background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 5px; padding: 5px 9px; selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
    border: 1px solid {FAINT};
}}
QLineEdit:hover, QDoubleSpinBox:hover, QSpinBox:hover {{ border-color: #3a3b40; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {FAINT}; background: {SURFACE}; }}

QComboBox {{ min-height: 20px; padding-right: 28px; combobox-popup: 0; }}
QComboBox:hover {{ background: {SURFACE_3}; border-color: #3a3b40; }}
QComboBox:on {{ border-color: {FAINT}; }}
QComboBox::drop-down {{ subcontrol-origin: padding; subcontrol-position: center right;
    width: 26px; border: none; }}
QComboBox::down-arrow {{ image: url({down}); width: 10px; height: 10px; }}
QComboBox::down-arrow:on {{ image: url({up}); }}
QComboBox::down-arrow:disabled {{ image: url({down_off}); }}
QComboBox QAbstractItemView {{ background: {SURFACE_2}; color: {TEXT}; padding: 4px;
    border: 1px solid #3a3b40; outline: none; selection-background-color: {SURFACE_3};
    selection-color: {TEXT}; }}
QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 0 10px; border-radius: 4px;
    border: none; }}
QComboBox QAbstractItemView::item:hover {{ background: {SURFACE_3}; }}
QComboBox QAbstractItemView::item:selected {{ background: {SURFACE_3}; color: {ACCENT}; }}
QComboBoxPrivateContainer {{ background: {SURFACE_2}; border: none; }}

QSpinBox, QDoubleSpinBox {{ padding-right: 26px; }}
QSpinBox::up-button, QDoubleSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::down-button {{ subcontrol-origin: border; width: 22px; border: none;
    border-left: 1px solid {BORDER}; background: transparent; }}
QSpinBox::up-button, QDoubleSpinBox::up-button {{ subcontrol-position: top right;
    border-top-right-radius: 5px; }}
QSpinBox::down-button, QDoubleSpinBox::down-button {{ subcontrol-position: bottom right;
    border-top: 1px solid {BORDER}; border-bottom-right-radius: 5px; }}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::down-button:hover {{ background: {SURFACE_3}; }}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{ image: url({up}); width: 8px; height: 8px; }}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ image: url({down}); width: 8px; height: 8px; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

QPushButton {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 5px; padding: 6px 13px; }}
QPushButton:hover {{ background: {SURFACE_3}; }}
QPushButton:pressed {{ background: {BORDER}; }}
QPushButton:disabled {{ color: {FAINT}; background: {SURFACE}; }}
QPushButton#primary {{ background: {ACCENT}; color: {ON_ACCENT}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {ACCENT_HI}; }}
QPushButton#primary:disabled {{ background: {SURFACE_2}; color: {FAINT}; }}
QPushButton#big {{ padding: 10px 16px; font: 600 10.5pt 'Segoe UI'; }}
QPushButton#stop {{ background: {SURFACE_2}; color: {ERR}; border: 1px solid {ERR};
    padding: 10px 16px; font: 600 10.5pt 'Segoe UI'; }}
QPushButton#stop:hover {{ background: #2a1d1c; }}
QPushButton#flat {{ background: transparent; border: none; color: {DIM}; padding: 4px 8px; }}
QPushButton#flat:hover {{ color: {TEXT}; }}
QPushButton#flat:checked {{ color: {TEXT}; }}
QPushButton#seg {{ background: transparent; border: none; color: {DIM};
    border-radius: 4px; padding: 4px 10px; }}
QPushButton#seg:hover {{ color: {TEXT}; }}
QPushButton#seg:checked {{ background: {SURFACE_3}; color: {TEXT}; }}
QFrame#segbar {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 5px; }}

QToolButton {{ background: transparent; border: none; color: {DIM}; padding: 4px; }}
QToolButton:hover {{ color: {TEXT}; }}
QToolButton#icon {{ background: {SURFACE_2}; border: 1px solid {BORDER}; border-radius: 5px;
    padding: 4px; }}
QToolButton#icon:hover {{ background: {SURFACE_3}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; border-radius: 6px; top: -1px; background: {SURFACE}; }}
QTabBar::tab {{ background: transparent; color: {DIM}; padding: 8px 16px; border: none; }}
QTabBar::tab:selected {{ color: {TEXT}; border-bottom: 2px solid {ACCENT}; }}
QTextEdit, QTextBrowser {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
    border-radius: 6px; padding: 8px; }}
QTextEdit#log {{ font-family: 'Consolas'; font-size: 9pt; background: #0d0e0f; }}
QCheckBox, QRadioButton {{ color: {TEXT}; spacing: 9px; padding: 3px 0; }}
QCheckBox:disabled, QRadioButton:disabled {{ color: {FAINT}; }}
QCheckBox::indicator, QRadioButton::indicator {{ width: 16px; height: 16px; }}
QCheckBox::indicator {{ background: {SURFACE_2}; border: 1px solid #4a4b50; border-radius: 4px; }}
QCheckBox::indicator:hover {{ border-color: {DIM}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url({check}); }}
QCheckBox::indicator:checked:hover {{ background: {ACCENT_HI}; border-color: {ACCENT_HI}; }}
QCheckBox::indicator:disabled {{ background: {SURFACE}; border-color: {BORDER}; }}
QRadioButton::indicator {{ background: {SURFACE_2}; border: 1px solid #4a4b50; border-radius: 8px; }}
QRadioButton::indicator:checked {{ border: 5px solid {ACCENT}; background: {ON_ACCENT}; }}
QSlider::groove:horizontal {{ height: 4px; background: {BORDER}; border-radius: 2px; }}
QSlider::handle:horizontal {{ width: 14px; margin: -6px 0; border-radius: 7px; background: {ACCENT}; }}
QScrollBar:vertical {{ background: transparent; width: 9px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {SURFACE_3}; border-radius: 4px; min-height: 24px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
QMenu {{ background: {SURFACE_2}; border: 1px solid #3a3b40; padding: 4px; }}
QMenu::item {{ padding: 7px 22px 7px 12px; border-radius: 4px; }}
QMenu::item:selected {{ background: {SURFACE_3}; }}
QMenu::item:disabled {{ color: {FAINT}; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}
QToolTip {{ background: {SURFACE_2}; color: {TEXT}; border: 1px solid {BORDER}; padding: 5px; }}
QDialogButtonBox QPushButton {{ min-width: 80px; }}
QPushButton QLabel {{ background: transparent; }}
QPushButton#primary QLabel {{ color: {ON_ACCENT}; font-weight: 600; }}
QPushButton#primary QLabel#key {{ background: rgba(0,0,0,0.12); border-color: rgba(0,0,0,0.18);
    color: {ON_ACCENT}; }}
QPushButton#stop QLabel {{ color: {ERR}; font-weight: 600; }}
QPushButton#stop QLabel#key {{ border-color: {ERR}; background: transparent; }}
QPushButton QLabel:disabled {{ color: {FAINT}; background: transparent; }}
"""

_sheet_cache: str | None = None


def _save_glyphs() -> dict[str, str]:
    """Check mark and chevrons as PNGs - Qt stylesheets can only draw them from files."""
    folder = Path(tempfile.gettempdir()) / "sublens-ui"
    folder.mkdir(exist_ok=True)

    def glyph(name, color, points, width):
        pm, p = _canvas(32)
        p.setPen(QPen(QColor(color), width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPolyline([QPointF(x, y) for x, y in points])
        p.end()
        path = folder / f"{name}.png"
        pm.save(str(path))
        return path.as_posix()

    return {
        "check": glyph("check", ON_ACCENT, [(8, 16.5), (13.5, 22), (24, 10.5)], 3.6),
        "down": glyph("down", DIM, [(7, 12), (16, 21), (25, 12)], 3.2),
        "up": glyph("up", DIM, [(7, 20), (16, 11), (25, 20)], 3.2),
        "down_off": glyph("down_off", FAINT, [(7, 12), (16, 21), (25, 12)], 3.2),
    }


class ComboPolish(QObject):
    """App-wide event filter: gives every combo box a list delegate, the only kind
    that honours the stylesheet's item rules (row height, hover, selection)."""

    def eventFilter(self, obj, ev):
        if (ev.type() == QEvent.Polish and isinstance(obj, QComboBox)
                and not isinstance(obj.itemDelegate(), QStyledItemDelegate)):
            obj.setItemDelegate(QStyledItemDelegate(obj))
        return False


def stylesheet() -> str:
    """The app stylesheet. Needs a QApplication (it paints its glyphs)."""
    global _sheet_cache
    if _sheet_cache is None:
        g = globals()
        _sheet_cache = _SHEET.format(**{k: g[k] for k in (
            "BG", "SURFACE", "SURFACE_2", "SURFACE_3", "BORDER", "TEXT", "DIM", "FAINT",
            "ACCENT", "ACCENT_HI", "ON_ACCENT", "OK", "WARN", "ERR")}, **_save_glyphs())
    return _sheet_cache


def _canvas(size: int):
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def dot_icon(color: str, size: int = 12) -> QIcon:
    pm, p = _canvas(size)
    p.setPen(Qt.NoPen)
    p.setBrush(QBrush(QColor(color)))
    p.drawEllipse(QRectF(2, 2, size - 4, size - 4))
    p.end()
    return QIcon(pm)


def dot_pixmap(color: str, size: int = 8) -> QPixmap:
    return dot_icon(color, size + 4).pixmap(size + 4, size + 4)


def swap_icon(size: int = 18) -> QIcon:
    """Two opposite arrows."""
    pm, p = _canvas(size)
    pen = QPen(QColor(TEXT), 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    s = size
    y1, y2 = s * 0.36, s * 0.66
    p.drawLine(QPointF(s * 0.2, y1), QPointF(s * 0.8, y1))
    p.drawLine(QPointF(s * 0.8, y1), QPointF(s * 0.64, y1 - s * 0.14))
    p.drawLine(QPointF(s * 0.8, y2), QPointF(s * 0.2, y2))
    p.drawLine(QPointF(s * 0.2, y2), QPointF(s * 0.36, y2 + s * 0.14))
    p.end()
    return QIcon(pm)


def app_icon(active: bool = False) -> QIcon:
    """A dark screen with two subtitle bars."""
    pm, p = _canvas(64)
    p.setPen(QPen(QColor("#45464c"), 1.5))
    p.setBrush(QBrush(QColor("#26272b")))
    p.drawRoundedRect(QRectF(4.75, 6.75, 54.5, 50.5), 10, 10)
    p.setPen(Qt.NoPen)
    bar = QColor(OK if active else ACCENT)
    p.setBrush(QBrush(bar))
    p.drawRoundedRect(QRectF(14, 34, 36, 6), 3, 3)
    bar.setAlpha(150)
    p.setBrush(QBrush(bar))
    p.drawRoundedRect(QRectF(20, 44, 24, 6), 3, 3)
    p.end()
    return QIcon(pm)
