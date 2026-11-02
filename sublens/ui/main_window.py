from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QObject, QTimer, Signal, QRectF, QLibraryInfo, QTranslator
from PySide6.QtGui import (QImage, QPixmap, QShortcut, QKeySequence, QPainter, QColor, QFont)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QFrame, QTextEdit, QToolButton, QMenu, QSystemTrayIcon, QInputDialog, QMessageBox,
    QButtonGroup, QDialog, QTextBrowser, QApplication, QSizePolicy, QScrollArea,
)

from .. import config, __version__, i18n
from ..capture import GRABBER
from ..engines import create_all
from ..i18n import t
from ..ocr import TEXT_STYLES
from ..pipeline import Scanner, Events
from ..textproc import text_score
from ..winutil import foreground_window
from . import theme
from .overlay import Overlay
from .region import RegionPicker
from .settings import SettingsDialog

try:
    import keyboard
    HAS_KEYBOARD = True
except Exception:  # pragma: no cover
    HAS_KEYBOARD = False

STYLE_LABELS = {"auto": "Auto", "subtitle": "Bright subtitle", "plain": "Dialog box"}


class Bridge(QObject):
    log = Signal(str, str)
    ocr = Signal(object)
    translated = Signal(str, str)
    cleared = Signal()
    busy = Signal(bool)
    status = Signal(str, str)
    hotkey = Signal(str)


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    img = img.convert("RGBA")
    qim = QImage(img.tobytes("raw", "RGBA"), img.width, img.height, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qim.copy())


# ---------------------------------------------------------------------------- widgets

class Monitor(QFrame):
    """The captured area, with the latest translation drawn on it like a subtitle."""

    def __init__(self):
        super().__init__()
        self.setObjectName("monitor")
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self._pm: QPixmap | None = None
        self._sub = ""
        self._empty = ""

    def set_image(self, pm: QPixmap | None):
        self._pm = pm
        self.update()

    def set_subtitle(self, text: str):
        self._sub = text
        self.update()

    def set_empty_text(self, text: str):
        self._empty = text
        self.update()

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        area = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self._pm and not self._pm.isNull():
            pm = self._pm.scaled(int(area.width()), int(area.height()),
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
            x = area.x() + (area.width() - pm.width()) / 2
            y = area.y() + (area.height() - pm.height()) / 2
            p.drawPixmap(int(x), int(y), pm)
        else:
            p.setPen(QColor(theme.FAINT))
            p.drawText(area, Qt.AlignCenter | Qt.TextWordWrap, self._empty)
        if self._sub:
            # dim band + white text with a black outline, like a real subtitle
            f = QFont("Segoe UI", 12, QFont.DemiBold)
            p.setFont(f)
            box = area.adjusted(18, 0, -18, -12)
            flags = Qt.AlignHCenter | Qt.AlignBottom | Qt.TextWordWrap
            br = p.boundingRect(box, flags, self._sub)
            band = br.adjusted(-10, -5, 10, 5)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 150))
            p.drawRoundedRect(band, 4, 4)
            p.setPen(QColor(0, 0, 0))
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)):
                p.drawText(box.translated(dx, dy), flags, self._sub)
            p.setPen(QColor("#ffffff"))
            p.drawText(box, flags, self._sub)
        p.end()


class KeyButton(QPushButton):
    """A button with its shortcut shown as a small keycap on the right."""

    def __init__(self, text: str, key: str = "", name: str = "", height: int = 40):
        super().__init__()
        if name:
            self.setObjectName(name)
        self.setCursor(Qt.PointingHandCursor)
        self._h = height
        h = QHBoxLayout(self)
        h.setContentsMargins(14, 0, 8, 0)
        h.setSpacing(12)
        self.label = QLabel(text)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        h.addWidget(self.label, 0, Qt.AlignVCenter)
        h.addStretch(1)
        if key:
            k = QLabel(key); k.setObjectName("key")
            k.setAttribute(Qt.WA_TransparentForMouseEvents)
            k.setFixedHeight(18)
            h.addWidget(k, 0, Qt.AlignVCenter)

    def set_text(self, text: str):
        self.label.setText(text)
        self.updateGeometry()

    def sizeHint(self):
        s = self.layout().sizeHint()
        s.setHeight(self._h)
        return s

    def minimumSizeHint(self):
        return self.sizeHint()


def repolish(w: QWidget):
    for x in [w] + w.findChildren(QWidget):
        x.style().unpolish(x)
        x.style().polish(x)


def section(title: str) -> QLabel:
    l = QLabel(title.upper())
    l.setObjectName("section")
    return l


def settings_list(rows: list) -> QFrame:
    """Grouped rows: (label, widget-or-layout) or a QWidget spanning the row."""
    f = QFrame(); f.setObjectName("list")
    f.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    v = QVBoxLayout(f)
    v.setContentsMargins(0, 0, 0, 0)
    v.setSpacing(0)
    for i, row in enumerate(rows):
        if i:
            d = QFrame(); d.setObjectName("divider")
            v.addWidget(d)
        h = QHBoxLayout()
        h.setContentsMargins(14, 9, 12, 9)
        h.setSpacing(10)
        if isinstance(row, QWidget):
            h.addWidget(row)
        else:
            label, ctl = row
            l = QLabel(label); l.setObjectName("rowlabel")
            l.setMinimumWidth(118)
            h.addWidget(l)
            if isinstance(ctl, QWidget):
                h.addWidget(ctl, 1)
            else:
                h.addLayout(ctl, 1)
        v.addLayout(h)
    return f


def segmented(labels: list[tuple[str, str]], group: QButtonGroup) -> QFrame:
    bar = QFrame(); bar.setObjectName("segbar")
    h = QHBoxLayout(bar)
    h.setContentsMargins(2, 2, 2, 2)
    h.setSpacing(2)
    for i, (key, text) in enumerate(labels):
        b = QPushButton(text)
        b.setObjectName("seg")
        b.setCheckable(True)
        b.setProperty("key", key)
        b.setCursor(Qt.PointingHandCursor)
        group.addButton(b, i)
        h.addWidget(b)
    return bar


# ---------------------------------------------------------------------------- window

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SubLens")
        self.setWindowIcon(theme.app_icon())
        self.resize(560, 800)
        self.setMinimumWidth(470)

        self.cfg = config.load()
        self._qt_tr = QTranslator(self)
        self._apply_language(self.cfg.get("ui_lang") or i18n.system_lang())
        self.engines = create_all()
        self.bridge = Bridge()
        ev = Events()
        ev.log = self.bridge.log.emit
        ev.ocr = self.bridge.ocr.emit
        ev.translated = self.bridge.translated.emit
        ev.cleared = self.bridge.cleared.emit
        ev.busy = self.bridge.busy.emit
        self.scanner = Scanner(self.cfg, self.engines, ev)

        self.overlay = Overlay(self.cfg)
        self.overlay.moved.connect(self._overlay_moved)
        self._idle_hide = QTimer(self, singleShot=True, timeout=self._hide_idle_overlay)
        self.picker = RegionPicker(self)
        self.picker.picked.connect(self._on_region)
        self.picker.finished.connect(self._restore_after_pick)

        self._target_hwnd = 0
        self._self_pid = os.getpid()
        self._hotkeys = []
        self._quitting = False
        self._tray = None
        self._status_sticky = False
        self._state = "idle"
        self._last_result = ("", "")
        self._last_frame: QPixmap | None = None
        self._log_html = ""

        self.setStyleSheet(theme.stylesheet())
        self._build()
        self._wire_bridge()
        self._setup_tray()
        if self.cfg.get("global_hotkeys") and HAS_KEYBOARD:
            self._register_hotkeys()
        for key, fn in (("F2", self._pick_region), ("F3", self._translate_once),
                        ("F4", self._toggle_scan), ("Escape", self.overlay.hide)):
            QShortcut(QKeySequence(key), self, activated=fn)

        self._pause_timer = QTimer(self, interval=700, timeout=self._check_auto_pause)
        self._pause_timer.start()

        self._refresh_region()
        self._check_ocr_ready()

    def _apply_language(self, lang: str):
        i18n.set_lang(lang)
        app = QApplication.instance()
        app.removeTranslator(self._qt_tr)
        # Qt's own strings (OK / Cancel / Yes / No, context menus)
        if lang == "tr" and self._qt_tr.load(
                "qtbase_tr", QLibraryInfo.path(QLibraryInfo.TranslationsPath)):
            app.installTranslator(self._qt_tr)

    # ======================================================================== UI
    def _build(self):
        central = QWidget()
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- top bar ------------------------------------------------------------
        top = QFrame(); top.setObjectName("topbar")
        h = QHBoxLayout(top)
        h.setContentsMargins(16, 10, 12, 10)
        h.setSpacing(8)
        logo = QLabel(); logo.setPixmap(theme.app_icon().pixmap(22, 22))
        name = QLabel("SubLens"); name.setObjectName("brand")
        self.state_dot = QLabel()
        self.state_lbl = QLabel(); self.state_lbl.setObjectName("state")
        h.addWidget(logo); h.addWidget(name); h.addSpacing(10)
        h.addWidget(self.state_dot); h.addWidget(self.state_lbl)
        h.addStretch(1)
        self.ui_lang_group = QButtonGroup(self)
        langbar = segmented([("en", "EN"), ("tr", "TR")], self.ui_lang_group)
        langbar.setToolTip(t("Interface language"))
        for b in self.ui_lang_group.buttons():
            b.setChecked(b.property("key") == i18n.lang())
        help_btn = QPushButton(t("Help")); help_btn.setObjectName("flat")
        help_btn.clicked.connect(self._open_help)
        set_btn = QPushButton(t("Settings")); set_btn.setObjectName("flat")
        set_btn.clicked.connect(self._open_settings)
        h.addWidget(langbar); h.addWidget(help_btn); h.addWidget(set_btn)
        outer.addWidget(top)

        # ---- page ---------------------------------------------------------------
        page = QWidget(); page.setObjectName("page")
        root = QVBoxLayout(page)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(8)
        scroll = QScrollArea(); scroll.setWidget(page); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(scroll, 1)

        # monitor
        self.monitor = Monitor()
        self.monitor.set_empty_text(t("No area selected yet.\nPress F2 and drag a box around "
                                      "the subtitles in your game."))
        self.monitor.set_image(self._last_frame)
        self.monitor.set_subtitle(self._last_result[1])
        root.addWidget(self.monitor)
        row = QHBoxLayout(); row.setSpacing(8)
        self.orig_lbl = QLabel(self._last_result[0] or t("The original text appears here."))
        self.orig_lbl.setObjectName("dim"); self.orig_lbl.setWordWrap(True)
        self.orig_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.view_btn = QPushButton(t("Filtered view")); self.view_btn.setObjectName("flat")
        self.view_btn.setCheckable(True)
        self.view_btn.setToolTip(t("Show the area the way the OCR sees it, after filtering"))
        self.tune_btn = QPushButton(t("Auto-tune")); self.tune_btn.setObjectName("flat")
        self.tune_btn.setToolTip(t("Tries every reading setting on the current frame and keeps "
                                   "the one that produces the cleanest text. Do it while a "
                                   "subtitle is visible."))
        row.addWidget(self.orig_lbl, 1)
        row.addWidget(self.view_btn, 0, Qt.AlignTop); row.addWidget(self.tune_btn, 0, Qt.AlignTop)
        root.addLayout(row)
        root.addSpacing(6)

        # actions
        row = QHBoxLayout(); row.setSpacing(8)
        self.start_btn = KeyButton(t("Start"), "F4", "primary")
        self.once_btn = KeyButton(t("Translate once"), "F3")
        row.addWidget(self.start_btn, 3); row.addWidget(self.once_btn, 2)
        root.addLayout(row)
        root.addSpacing(10)

        # source
        root.addWidget(section(t("Screen")))
        area = QHBoxLayout(); area.setSpacing(8)
        self.region_lbl = QLabel(); self.region_lbl.setObjectName("dim")
        self.pick_btn = KeyButton(t("Select"), "F2", height=32)
        area.addWidget(self.region_lbl, 1); area.addWidget(self.pick_btn)
        style = QHBoxLayout(); style.setSpacing(8)
        self.style_group = QButtonGroup(self)
        style.addWidget(segmented([(k, t(STYLE_LABELS[k])) for k, _ in TEXT_STYLES],
                                  self.style_group))
        for b in self.style_group.buttons():
            b.setToolTip(t(dict(TEXT_STYLES)[b.property("key")]))
        style.addStretch(1)
        root.addWidget(settings_list([(t("Subtitle area"), area), (t("Text style"), style)]))
        self._sync_style_buttons()
        root.addSpacing(10)

        # translation
        root.addWidget(section(t("Translation")))
        langs = QHBoxLayout(); langs.setSpacing(6)
        self.src = QComboBox(); self.tgt = QComboBox()
        for name in config.SRC_LANGS:
            self.src.addItem(t(name), name)
        for name in config.LANGS:
            self.tgt.addItem(t(name), name)
        self.src.setCurrentIndex(max(0, self.src.findData(self.cfg["src_lang"])))
        self.tgt.setCurrentIndex(max(0, self.tgt.findData(self.cfg["tgt_lang"])))
        self.swap_btn = QToolButton(); self.swap_btn.setObjectName("icon")
        self.swap_btn.setIcon(theme.swap_icon()); self.swap_btn.setToolTip(t("Swap languages"))
        langs.addWidget(self.src, 1); langs.addWidget(self.swap_btn); langs.addWidget(self.tgt, 1)
        self.engine = QComboBox()
        for key, eng in self.engines.items():
            self.engine.addItem(theme.dot_icon(theme.ENGINE_COLOR.get(key, theme.DIM)),
                                t(eng.name), key)
        self.engine.setCurrentIndex(max(0, self.engine.findData(self.cfg["engine"])))
        self.engine_note = QLabel(); self.engine_note.setObjectName("hint")
        self.engine_note.setWordWrap(True)
        root.addWidget(settings_list([(t("Languages"), langs), (t("Translator"), self.engine),
                                      self.engine_note]))
        root.addSpacing(10)

        # game
        root.addWidget(section(t("Game")))
        prof = QHBoxLayout(); prof.setSpacing(8)
        self.profile_combo = QComboBox()
        self.profile_combo.setToolTip(t("Game profiles remember the area and reading settings "
                                        "per game, and switch automatically when that game "
                                        "is active."))
        self.profile_btn = QPushButton(t("Manage"))
        pm = QMenu(self)
        pm.addAction(t("Save current settings as a game profile…"), self._save_profile)
        pm.addAction(t("Delete this profile"), self._delete_profile)
        self.profile_btn.setMenu(pm)
        prof.addWidget(self.profile_combo, 1); prof.addWidget(self.profile_btn)
        root.addWidget(settings_list([(t("Game profile"), prof)]))

        # log
        self.log_box = QTextEdit(); self.log_box.setObjectName("log"); self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(170); self.log_box.hide()
        if self._log_html:
            self.log_box.setHtml(self._log_html)
        root.addSpacing(6)
        root.addWidget(self.log_box)
        root.addStretch(1)

        # ---- bottom bar ---------------------------------------------------------
        bottom = QFrame(); bottom.setObjectName("bottombar")
        h = QHBoxLayout(bottom); h.setContentsMargins(16, 6, 10, 6)
        self.status_lbl = QLabel(""); self.status_lbl.setObjectName("hint")
        self.log_btn = QPushButton(t("Show log")); self.log_btn.setObjectName("flat")
        self.log_btn.setCheckable(True)
        h.addWidget(self.status_lbl, 1); h.addWidget(self.log_btn)
        outer.addWidget(bottom)

        old = self.centralWidget()
        self.setCentralWidget(central)
        if old is not None:
            old.deleteLater()

        self._reload_profiles()
        self._update_engine_note()
        self._set_state(self._state)
        self._wire_widgets()

    def _wire_bridge(self):
        b = self.bridge
        b.log.connect(self._log)
        b.ocr.connect(self._on_ocr)
        b.translated.connect(self._on_translated)
        b.cleared.connect(self._on_cleared)
        b.busy.connect(lambda busy: self._set_status(t("Translating…") if busy else "", theme.DIM)
                       if not self._status_sticky else None)
        b.status.connect(self._set_status)
        b.hotkey.connect(self._on_hotkey)

    def _wire_widgets(self):
        self.pick_btn.clicked.connect(self._pick_region)
        self.start_btn.clicked.connect(self._toggle_scan)
        self.once_btn.clicked.connect(self._translate_once)
        self.tune_btn.clicked.connect(self._auto_tune)
        self.log_btn.toggled.connect(self._toggle_log)
        self.view_btn.toggled.connect(lambda _: self._refresh_preview())
        self.src.currentIndexChanged.connect(self._on_lang)
        self.tgt.currentIndexChanged.connect(self._on_lang)
        self.swap_btn.clicked.connect(self._swap_langs)
        self.engine.currentIndexChanged.connect(self._on_engine)
        self.style_group.idClicked.connect(self._on_style)
        self.profile_combo.activated.connect(self._on_profile_chosen)
        self.ui_lang_group.idClicked.connect(
            lambda i: self._set_ui_lang(self.ui_lang_group.button(i).property("key")))

    def _set_ui_lang(self, lang: str):
        if lang == i18n.lang():
            return
        self.cfg["ui_lang"] = lang
        self._save()
        self._apply_language(lang)
        self._retranslate()

    def _retranslate(self):
        self._log_html = self.log_box.toHtml()
        log_open = self.log_box.isVisible()
        self._build()
        self.log_btn.setChecked(log_open)
        self._refresh_region()
        self._check_ocr_ready()
        if self._tray:
            self._tray.setContextMenu(self._tray_menu())

    def _toggle_log(self, on: bool):
        self.log_box.setVisible(on)
        self.log_btn.setText(t("Hide log") if on else t("Show log"))

    # ================================================================== helpers
    def _save(self):
        config.save(self.cfg)

    def _log(self, msg: str, tag: str = "dim"):
        col = {"ok": theme.OK, "warn": theme.WARN, "err": theme.ERR,
               "tr": theme.TEXT}.get(tag, theme.DIM)
        html = msg.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        self.log_box.append(f'<span style="color:{theme.FAINT}">{time.strftime("%H:%M:%S")}</span> '
                            f'<span style="color:{col}">{html}</span>')
        if tag in ("err", "warn"):
            self._set_status(msg[:140], theme.ERR if tag == "err" else theme.WARN, sticky=True)

    def _set_status(self, text: str, color: str, sticky: bool = False):
        self.status_lbl.setText(text)
        self.status_lbl.setToolTip(text)
        self.status_lbl.setStyleSheet(f"color: {color};")
        self._status_sticky = sticky
        if sticky:
            QTimer.singleShot(6000, lambda: setattr(self, "_status_sticky", False))

    def _set_state(self, state: str):
        """idle | run | pause - drives the top bar and the start button."""
        self._state = state
        text, col = {"idle": (t("Idle"), theme.FAINT), "run": (t("Reading"), theme.OK),
                     "pause": (t("Paused"), theme.WARN)}[state]
        self.state_dot.setPixmap(theme.dot_pixmap(col))
        self.state_lbl.setText(text)
        self.state_lbl.setStyleSheet(f"color: {col if state != 'idle' else theme.DIM};")
        running = state != "idle"
        self.start_btn.set_text(t("Stop") if running else t("Start"))
        self.start_btn.setObjectName("stop" if running else "primary")
        repolish(self.start_btn)
        if self._tray:
            self._tray.setIcon(theme.app_icon(running))

    def _check_ocr_ready(self):
        try:
            self.scanner.reader.check(self.cfg["src_lang"])
            self._set_status(t("Ready · Windows OCR"), theme.DIM)
        except Exception as e:
            self._log(str(e), "err")

    # ================================================================== region
    def _pick_region(self):
        if self.picker.active:
            return
        self._was_visible = self.isVisible() and not self.isMinimized()
        self.overlay.hide()
        self.hide()
        QTimer.singleShot(250, self.picker.start)

    def _restore_after_pick(self):
        if getattr(self, "_was_visible", True):
            self.showNormal()
            self.activateWindow()

    def _on_region(self, region):
        self.cfg["region"] = list(region)
        self._save()
        self.scanner.settler.reset()
        self._refresh_region()
        self._log(t("Area: {}", region), "ok")

    def _refresh_region(self):
        r = self.cfg.get("region")
        ok = bool(r)
        for w in (self.start_btn, self.once_btn, self.tune_btn, self.view_btn):
            w.setEnabled(ok)
        if ok:
            self.region_lbl.setText(f"{r[2]-r[0]} × {r[3]-r[1]} px")
            self.pick_btn.set_text(t("Change"))
            QTimer.singleShot(120, self._refresh_preview)
        else:
            self.region_lbl.setText(t("Not selected"))
            self.pick_btn.set_text(t("Select"))

    def _refresh_preview(self):
        if not self.cfg.get("region"):
            return
        if self.view_btn.isChecked():
            self._translate_preview_only()
            return
        try:
            self._show_preview(GRABBER.grab(self.cfg["region"]))
        except Exception as e:
            self._log(t("Preview failed: {}", e), "warn")

    def _translate_preview_only(self):
        def run():
            try:
                self.bridge.ocr.emit(self.scanner.read_once())
            except Exception as e:
                self.bridge.log.emit(str(e), "err")
        threading.Thread(target=run, daemon=True).start()

    def _show_preview(self, img: Image.Image):
        self._last_frame = pil_to_pixmap(img)
        self.monitor.set_image(self._last_frame)

    # ================================================================== options
    def _on_lang(self):
        self.cfg["src_lang"] = self.src.currentData()
        self.cfg["tgt_lang"] = self.tgt.currentData()
        self.scanner.settler.reset()
        self.scanner.roller.reset()
        self._save()
        self._check_ocr_ready()
        if self.cfg["src_lang"] == self.cfg["tgt_lang"]:
            self._log(t("Source and target language are the same."), "warn")

    def _swap_langs(self):
        src, tgt = self.cfg["src_lang"], self.cfg["tgt_lang"]
        if src not in config.LANGS:     # Auto-Detect can't be a target
            return
        for combo, val in ((self.src, tgt), (self.tgt, src)):
            combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(val)))
            combo.blockSignals(False)
        self._on_lang()

    def _on_engine(self):
        self.cfg["engine"] = self.engine.currentData()
        self.scanner.settler.reset()
        self.overlay.restyle()
        self._update_engine_note()
        self._save()

    def _update_engine_note(self):
        eng = self.engines[self.cfg["engine"]]
        note = t(eng.note)
        if not eng.is_llm:
            note += "  " + t("Only AI engines translate short replies from the conversation's context.")
        self.engine_note.setText(note)

    def _on_style(self, idx: int):
        self.cfg["text_style"] = self.style_group.button(idx).property("key")
        self.scanner.settler.reset()
        self._save()
        if self.view_btn.isChecked():
            self._refresh_preview()

    def _sync_style_buttons(self):
        for b in self.style_group.buttons():
            b.setChecked(b.property("key") == self.cfg.get("text_style", "auto"))

    # ================================================================== run
    def _toggle_scan(self):
        if self.scanner.running:
            self.scanner.stop()
            self.overlay.hide()
            self._set_state("idle")
            self._log(t("Stopped."), "dim")
            self._set_status(t("Stopped"), theme.DIM)
            return
        if not self.cfg.get("region"):
            self._pick_region()
            return
        self._target_hwnd = 0
        hwnd, pid, title, exe = foreground_window()
        if pid and pid != self._self_pid:
            self._lock_target(hwnd, title, exe)
        self.scanner.start()
        self._set_state("run")
        self._log(t("Started · {}", t(self.engines[self.cfg["engine"]].name)), "ok")
        self._set_status(t("Reading… switch to your game"), theme.OK)

    def _translate_once(self):
        if not self.cfg.get("region"):
            self._pick_region()
            return
        self.scanner.translate_once()

    def _on_ocr(self, res):
        if self.view_btn.isChecked():
            self._show_preview(res.processed)
        elif not self.scanner.running:
            self._refresh_preview()

    def _on_translated(self, src: str, tr: str):
        self._last_result = (src, tr)
        self.orig_lbl.setText(src)
        self.monitor.set_subtitle(tr)
        if self.scanner.running and not self.view_btn.isChecked():
            self._refresh_preview()
        if self.cfg.get("show_overlay", True):
            self.overlay.show_translation(tr, src, self.scanner.text_region(src))
            if not self.scanner.running:
                # a one-off translation (F3): nothing will clear it, so it goes on its own
                self._idle_hide.start(max(6000, 1500 + 60 * len(tr)))

    def _hide_idle_overlay(self):
        if not self.scanner.running:
            self.overlay.hide()

    def _on_cleared(self):
        self.overlay.hide()
        self.monitor.set_subtitle("")

    def _overlay_moved(self, x, y):
        if self.cfg.get("overlay_position") != "fixed":
            self._log(t("Overlay pinned where you dropped it (Settings > Overlay to change)."), "dim")
        self.cfg["overlay_position"] = "fixed"
        self.cfg["overlay_xy"] = [x, y]
        self._save()

    # ================================================================== auto-tune
    def _auto_tune(self):
        if not self.cfg.get("region"):
            return
        self.tune_btn.setEnabled(False)
        self._set_status(t("Trying reading settings…"), theme.WARN, sticky=True)
        threading.Thread(target=self._auto_tune_worker, daemon=True).start()

    def _auto_tune_worker(self):
        reader = self.scanner.reader
        lang = self.cfg["src_lang"]
        try:
            img = GRABBER.grab(self.cfg["region"])
            best = None
            for style in ("auto", "subtitle", "plain"):
                for scale in (1, 2, 3):
                    try:
                        res = reader.read(img, lang, style, scale)
                    except Exception as e:
                        self.bridge.log.emit(str(e), "err")
                        return
                    score = text_score(res.text)
                    self.bridge.log.emit(f"[{style}/{scale}x] {score:.0f}: {res.text[:60]}", "dim")
                    if best is None or score > best[0]:
                        best = (score, style, scale, res)
            if not best or best[0] <= 0:
                self.bridge.status.emit(t("No readable text found - make sure a subtitle is on "
                                          "screen while tuning."), theme.ERR)
                return
            score, style, scale, res = best
            self.cfg["text_style"] = style
            self.cfg["ocr_scale"] = scale
            self.bridge.ocr.emit(res)
            self.bridge.status.emit(t("Best: {} · {}x  →  “{}”", t(STYLE_LABELS[style]), scale,
                                      res.text[:50]), theme.OK)
        finally:
            QTimer.singleShot(0, self._after_tune)

    def _after_tune(self):
        self.tune_btn.setEnabled(True)
        self._sync_style_buttons()
        self._save()

    # ================================================================== profiles
    def _reload_profiles(self):
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        self.profile_combo.addItem(t("None"), "")
        for name in sorted(self.cfg.get("profiles", {})):
            self.profile_combo.addItem(name, name)
        idx = self.profile_combo.findData(self.cfg.get("profile", ""))
        self.profile_combo.setCurrentIndex(max(0, idx))
        self.profile_combo.blockSignals(False)

    def _save_profile(self):
        exe = getattr(self, "_last_game_exe", "") or ""
        name, ok = QInputDialog.getText(self, t("Save game profile"),
                                        t("Profile name (e.g. the game's name):"),
                                        text=self.cfg.get("profile") or Path(exe).stem)
        if not ok or not name.strip():
            return
        name = name.strip()
        if exe:
            bind = QMessageBox.question(
                self, t("Switch automatically?"),
                t("Use this profile automatically whenever {} is the active game?", exe))
            if bind != QMessageBox.Yes:
                exe = ""
        self.cfg.setdefault("profiles", {})[name] = config.snapshot_profile(self.cfg, exe)
        self.cfg["profile"] = name
        self._save()
        self._reload_profiles()
        self._log(t("Profile saved: {}", name) + (f" ({exe})" if exe else ""), "ok")

    def _delete_profile(self):
        name = self.profile_combo.currentData()
        if not name:
            return
        self.cfg["profiles"].pop(name, None)
        self.cfg["profile"] = ""
        self._save()
        self._reload_profiles()

    def _on_profile_chosen(self, _idx):
        self._activate_profile(self.profile_combo.currentData())

    def _activate_profile(self, name: str):
        prof = self.cfg.get("profiles", {}).get(name)
        self.cfg["profile"] = name or ""
        if prof:
            config.apply_profile(self.cfg, prof)
            self.src.blockSignals(True)
            self.src.setCurrentIndex(max(0, self.src.findData(self.cfg["src_lang"])))
            self.src.blockSignals(False)
            self._sync_style_buttons()
            self.scanner.settler.reset()
            self.scanner.translator.clear_cache()
            self._refresh_region()
            self._log(t("Profile: {}", name), "ok")
        self._reload_profiles()
        self._save()

    # ================================================================== auto-pause
    def _lock_target(self, hwnd, title, exe):
        self._target_hwnd = hwnd
        self._last_game_exe = exe
        self._log(t("Game window: {}", title[:40] or exe or "?"), "dim")
        prof = config.profile_for_exe(self.cfg, exe)
        if prof and prof != self.cfg.get("profile"):
            self._activate_profile(prof)

    def _check_auto_pause(self):
        if not self.scanner.running:
            return
        hwnd, pid, title, exe = foreground_window()
        if not hwnd or pid == self._self_pid:
            return
        if not self._target_hwnd:
            self._lock_target(hwnd, title, exe)
        if not self.cfg.get("auto_pause", True):
            if self.scanner.paused:
                self.scanner.paused = False
                self._set_state("run")
            return
        paused = hwnd != self._target_hwnd
        if paused != self.scanner.paused:
            self.scanner.paused = paused
            self._set_state("pause" if paused else "run")
            self._set_status(t("Paused - game not active") if paused else t("Reading…"),
                             theme.WARN if paused else theme.OK)

    # ================================================================== hotkeys
    def _register_hotkeys(self):
        self._unregister_hotkeys()
        emit = self.bridge.hotkey.emit
        try:
            for combo, action in (("f2", "pick"), ("f3", "once"), ("f4", "toggle"),
                                  ("ctrl+alt+r", "pick"), ("ctrl+alt+t", "once"),
                                  ("ctrl+alt+g", "toggle"), ("ctrl+alt+h", "hide")):
                self._hotkeys.append(keyboard.add_hotkey(combo, lambda a=action: emit(a)))
        except Exception as e:
            self._log(t("Global shortcuts unavailable: {}", e), "warn")

    def _unregister_hotkeys(self):
        for h in self._hotkeys:
            try:
                keyboard.remove_hotkey(h)
            except Exception:
                pass
        self._hotkeys = []

    def _on_hotkey(self, action: str):
        # window-local shortcuts already handle keys while we are focused
        if self.isActiveWindow() and action in ("pick", "once", "toggle"):
            return
        {"pick": self._pick_region, "once": self._translate_once,
         "toggle": self._toggle_scan, "hide": self.overlay.hide}[action]()

    # ================================================================== dialogs
    def _open_settings(self):
        dlg = SettingsDialog(self.cfg, self.engines, self.scanner.reader, self)
        dlg.setStyleSheet(theme.stylesheet())
        if dlg.exec() != QDialog.Accepted:
            return
        old_hotkeys = self.cfg.get("global_hotkeys")
        old_lang = i18n.lang()
        new = dlg.cfg
        glossary_changed = (new.get("glossary") != self.cfg.get("glossary")
                            or new.get("ctx") != self.cfg.get("ctx"))
        self.cfg.clear()
        self.cfg.update(new)          # same dict object: scanner sees the change
        if glossary_changed:
            self.scanner.translator.clear_cache()
        if HAS_KEYBOARD and self.cfg.get("global_hotkeys") != old_hotkeys:
            self._register_hotkeys() if self.cfg.get("global_hotkeys") else self._unregister_hotkeys()
        self.overlay.restyle()
        self._save()
        self._apply_language(self.cfg.get("ui_lang") or i18n.system_lang())
        if i18n.lang() != old_lang:
            self._retranslate()
        else:
            self.engine.setCurrentIndex(max(0, self.engine.findData(self.cfg["engine"])))
            self._sync_style_buttons()
            self._check_ocr_ready()
        self._set_status(t("Settings saved"), theme.OK)

    def _open_help(self):
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Help") + " · SubLens")
        dlg.resize(700, 660)
        dlg.setStyleSheet(theme.stylesheet())
        tb = QTextBrowser(); tb.setOpenExternalLinks(True)
        names = ["READMEapp.md"] if i18n.lang() == "tr" else ["READMEapp.en.md", "READMEapp.md"]
        md = ""
        for name in names:
            for base in (Path(__file__).resolve().parents[2], Path(getattr(sys, "_MEIPASS", "."))):
                p = base / name
                if p.exists() and not md:
                    md = p.read_text(encoding="utf-8")
        tb.setMarkdown(md or "README not found.")
        v = QVBoxLayout(dlg); v.addWidget(tb)
        ver = QLabel(f"SubLens {__version__}"); ver.setObjectName("hint")
        v.addWidget(ver)
        dlg.exec()

    # ================================================================== tray / quit
    def _tray_menu(self) -> QMenu:
        m = QMenu(self)
        m.addAction(t("Show / hide"), self._toggle_visible)
        m.addAction(t("Start / stop"), self._toggle_scan)
        m.addAction(t("Hide overlay"), self.overlay.hide)
        m.addSeparator()
        m.addAction(t("Quit"), self._quit)
        return m

    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray = QSystemTrayIcon(theme.app_icon(False), self)
        self._tray.setToolTip("SubLens")
        self._tray.setContextMenu(self._tray_menu())
        self._tray.activated.connect(
            lambda r: self._toggle_visible() if r in (QSystemTrayIcon.Trigger,
                                                      QSystemTrayIcon.DoubleClick) else None)
        self._tray.show()

    def _toggle_visible(self):
        if self.isVisible() and not self.isMinimized():
            self.hide()
        else:
            self.showNormal(); self.activateWindow(); self.raise_()

    def _quit(self):
        self._quitting = True
        self.close()

    def closeEvent(self, e):
        if self._tray and self.cfg.get("minimize_to_tray", True) and not self._quitting:
            e.ignore()
            self.hide()
            if self.cfg.get("notifications", True):
                self._tray.showMessage("SubLens",
                                       t("Still running in the tray · right-click it to quit"),
                                       theme.app_icon(self.scanner.running), 2500)
            return
        self.scanner.shutdown()
        self._pause_timer.stop()
        if HAS_KEYBOARD:
            self._unregister_hotkeys()
            try:
                keyboard.unhook_all()
            except Exception:
                pass
        self._save()
        self.overlay.close()
        if self._tray:
            self._tray.hide()
        super().closeEvent(e)
        QApplication.instance().quit()
        # keyboard's listener thread is non-daemon; make sure the process ends
        QTimer.singleShot(800, lambda: os._exit(0))
