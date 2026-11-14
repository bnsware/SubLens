"""Translation overlay drawn on top of the game.

Its width follows the subtitle area, so a two-line subtitle comes out as a
two-line translation instead of one long strip. It is excluded from screen
capture so it can never be read back by OCR, even when it covers the area.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal
from PySide6.QtGui import QGuiApplication, QColor
from PySide6.QtWidgets import QWidget, QLabel, QVBoxLayout, QFrame, QGraphicsDropShadowEffect

from . import theme
from .screens import to_logical
from ..winutil import exclude_from_capture


class Overlay(QWidget):
    moved = Signal(int, int)   # user dragged it -> fixed position

    def __init__(self, cfg: dict):
        super().__init__(None)
        self.cfg = cfg
        self._drag = None
        self._region = None
        self._click_through = None
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setCursor(Qt.OpenHandCursor)    # shows it can be dragged
        self._apply_flags()

        self.card = QFrame(self)
        self.card.setObjectName("ovCard")
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 170))
        self.card.setGraphicsEffect(shadow)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.addWidget(self.card)
        lay = QVBoxLayout(self.card)
        lay.setContentsMargins(16, 10, 16, 12)
        lay.setSpacing(4)
        self.orig = QLabel()
        self.orig.setWordWrap(True)
        self.orig.setAlignment(Qt.AlignCenter)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setAlignment(Qt.AlignCenter)
        self.text.setTextInteractionFlags(Qt.NoTextInteraction)
        lay.addWidget(self.orig)
        lay.addWidget(self.text)
        self.restyle()

    # -- appearance -----------------------------------------------------------
    def _apply_flags(self):
        ct = bool(self.cfg.get("overlay_click_through"))
        if ct == self._click_through:
            return
        self._click_through = ct
        flags = Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        if ct:
            flags |= Qt.WindowTransparentForInput
        visible = self.isVisible()
        self.setWindowFlags(flags)
        if visible:
            self.show()

    def restyle(self, engine: str | None = None):
        self._apply_flags()
        a = int(255 * float(self.cfg.get("overlay_opacity", 0.88)))
        self.card.setStyleSheet(
            f"QFrame#ovCard {{ background: rgba(14, 14, 15, {a}); "
            f"border: 1px solid rgba(255, 255, 255, 28); border-radius: 6px; }}")
        fs = int(self.cfg.get("overlay_font", 15))
        self.text.setStyleSheet(f"color: {theme.TEXT}; background: transparent; "
                                f"font: 600 {fs}pt 'Segoe UI';")
        self.orig.setStyleSheet(f"color: {theme.DIM}; background: transparent; "
                                f"font: {max(8, fs - 5)}pt 'Segoe UI';")

    def showEvent(self, e):
        super().showEvent(e)
        exclude_from_capture(int(self.winId()))

    # -- content ----------------------------------------------------------------
    def show_translation(self, translation: str, original: str, region):
        self.restyle()
        show_orig = bool(self.cfg.get("overlay_show_original")) and original and original != translation
        self.orig.setVisible(bool(show_orig))
        self.orig.setText(original if show_orig else "")
        self.text.setText(translation)

        if region:
            area, scr = to_logical(region)
        else:
            area, scr = QRect(self.x(), self.y(), self.width(), 60), self.screen()
        sg = scr.availableGeometry()
        # as wide as the subtitle text itself -> wraps into as many lines as the original
        w = max(360, min(area.width() + 72, sg.width() - 40))
        inner = w - 20 - 32
        self.text.setFixedWidth(inner)
        self.orig.setFixedWidth(inner)
        self.card.layout().activate()
        self.layout().activate()
        h = self.sizeHint().height()

        pos = self.cfg.get("overlay_position", "above")
        xy = self.cfg.get("overlay_xy")
        if self._drag is not None:          # being dragged: don't snap it back
            x, y = self.x(), self.y()
        elif pos == "fixed" and xy:
            x, y = xy
        else:
            x = area.center().x() - w // 2
            if pos == "below":
                y = area.bottom() + 6
            else:
                y = area.top() - h - 6
                if y < sg.top():
                    y = area.bottom() + 6
        x = max(sg.left(), min(x, sg.right() - w))
        y = max(sg.top(), min(y, sg.bottom() - h))
        self.setGeometry(x, y, w, h)
        self.show()
        self.raise_()

    # -- dragging ---------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self.setCursor(Qt.ClosedHandCursor)
            self.grabMouse()
        elif e.button() == Qt.RightButton:
            self.hide()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _):
        if self._drag is not None:
            self._drag = None
            self.releaseMouse()
            self.setCursor(Qt.OpenHandCursor)
            self.moved.emit(self.x(), self.y())

    def hideEvent(self, e):
        if self._drag is not None:
            self._drag = None
            self.releaseMouse()
        super().hideEvent(e)
