from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPalette, QColor
from PySide6.QtWidgets import QApplication

from .ui import theme
from .ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)  # keep running in the tray

    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    ico = base / "SubLens.ico"
    app.setWindowIcon(QIcon(str(ico)) if ico.exists() else theme.app_icon())

    pal = app.palette()
    for role, col in ((QPalette.Window, theme.BG), (QPalette.Base, theme.SURFACE_2),
                      (QPalette.Text, theme.TEXT), (QPalette.WindowText, theme.TEXT),
                      (QPalette.Highlight, theme.ACCENT), (QPalette.HighlightedText, "#ffffff")):
        pal.setColor(role, QColor(col))
    app.setPalette(pal)
    combo_polish = theme.ComboPolish(app)
    app.installEventFilter(combo_polish)
    app.setStyleSheet(theme.stylesheet())

    win = MainWindow()
    win.show()
    code = app.exec()
    for stream in (sys.stdout, sys.stderr):
        if stream:          # None in the windowed exe
            stream.flush()
    # the `keyboard` hook thread is non-daemon and would keep the process alive
    os._exit(code)
