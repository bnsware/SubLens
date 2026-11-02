"""Map between Qt logical coordinates and physical screen pixels.

Qt works in DPI-scaled logical pixels; screen capture works in physical pixels.
At 125-150 % Windows scaling the two differ, so every region has to be converted.
"""
from __future__ import annotations

from PySide6.QtCore import QRect, QPoint
from PySide6.QtGui import QGuiApplication, QScreen

from ..winutil import monitor_rects


def _phys_origin(screen: QScreen) -> tuple[int, int]:
    rect = monitor_rects().get(screen.name())
    if rect:
        return rect[0], rect[1]
    g = screen.geometry()
    return g.x(), g.y()


def to_physical(screen: QScreen, r: QRect) -> tuple[int, int, int, int]:
    """Global logical rect on `screen` -> physical (x1, y1, x2, y2)."""
    g = screen.geometry()
    dpr = screen.devicePixelRatio()
    ox, oy = _phys_origin(screen)
    x1 = ox + round((r.left() - g.x()) * dpr)
    y1 = oy + round((r.top() - g.y()) * dpr)
    x2 = ox + round((r.left() + r.width() - g.x()) * dpr)
    y2 = oy + round((r.top() + r.height() - g.y()) * dpr)
    return x1, y1, x2, y2


def to_logical(region) -> tuple[QRect, QScreen]:
    """Physical region -> (logical QRect, screen it lives on)."""
    x1, y1, x2, y2 = region
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
    mons = monitor_rects()
    for scr in QGuiApplication.screens():
        m = mons.get(scr.name())
        if m and m[0] <= cx < m[2] and m[1] <= cy < m[3]:
            dpr = scr.devicePixelRatio()
            g = scr.geometry()
            lx = g.x() + (x1 - m[0]) / dpr
            ly = g.y() + (y1 - m[1]) / dpr
            return QRect(round(lx), round(ly), round((x2 - x1) / dpr), round((y2 - y1) / dpr)), scr
    scr = QGuiApplication.screenAt(QPoint(int(cx), int(cy))) or QGuiApplication.primaryScreen()
    return QRect(x1, y1, x2 - x1, y2 - y1), scr
