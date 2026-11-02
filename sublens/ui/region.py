"""Drag-to-select the subtitle area. One window per monitor (mixed-DPI safe)."""
from __future__ import annotations

from PySide6.QtCore import Qt, QObject, QRect, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QGuiApplication
from PySide6.QtWidgets import QWidget

from . import theme
from .screens import to_physical
from ..i18n import t


class _ScreenSelector(QWidget):
    picked = Signal(tuple)
    cancelled = Signal()

    def __init__(self, screen):
        super().__init__(None)
        self._screen = screen
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setCursor(Qt.CrossCursor)
        self.setGeometry(screen.geometry())
        self._start = self._end = None

    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(0, 0, 0, 120))
        p.setFont(QFont("Segoe UI", 13, QFont.DemiBold))
        p.setPen(QColor(theme.TEXT))
        p.drawText(self.rect().adjusted(0, 36, 0, 0), Qt.AlignHCenter | Qt.AlignTop,
                   t("Drag a box around where the subtitles appear  ·  "
                     "include both lines and some margin  ·  Esc to cancel"))
        if self._start and self._end:
            r = QRect(self._start, self._end).normalized()
            p.setCompositionMode(QPainter.CompositionMode_Clear)
            p.fillRect(r, Qt.transparent)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor(theme.ACCENT_HI), 2))
            p.drawRect(r)
            p.setFont(QFont("Consolas", 10, QFont.Bold))
            dpr = self._screen.devicePixelRatio()
            p.drawText(r.left() + 4, r.top() - 8,
                       f"{round(r.width() * dpr)} × {round(r.height() * dpr)}")

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._start = self._end = e.position().toPoint()
            self.update()
        elif e.button() == Qt.RightButton:
            self.cancelled.emit()

    def mouseMoveEvent(self, e):
        if self._start:
            self._end = e.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.LeftButton or not self._start:
            return
        r = QRect(self._start, e.position().toPoint()).normalized()
        self._start = None
        if r.width() < 30 or r.height() < 12:
            self.update()
            return
        r.translate(self.geometry().topLeft())
        self.picked.emit(to_physical(self._screen, r))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancelled.emit()


class RegionPicker(QObject):
    """Shows a selector on every screen; emits the physical region or nothing."""
    picked = Signal(tuple)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._wins: list[_ScreenSelector] = []

    @property
    def active(self) -> bool:
        return bool(self._wins)

    def start(self):
        if self._wins:
            return
        for scr in QGuiApplication.screens():
            w = _ScreenSelector(scr)
            w.picked.connect(self._on_pick)
            w.cancelled.connect(self._close)
            w.show()
            self._wins.append(w)
        under = QGuiApplication.screenAt(self._wins[0].cursor().pos())
        for w in self._wins:
            if w._screen is under:
                w.activateWindow()
                w.setFocus()

    def _on_pick(self, region):
        self._close()
        self.picked.emit(region)

    def _close(self):
        for w in self._wins:
            w.close()
        self._wins = []
        self.finished.emit()
