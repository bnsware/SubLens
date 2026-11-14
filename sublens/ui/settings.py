"""Settings dialog. Edits a copy of the config; the caller applies it on accept."""
from __future__ import annotations

import copy
import threading

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QTabWidget, QWidget, QLabel,
    QLineEdit, QComboBox, QPushButton, QCheckBox, QSpinBox, QDoubleSpinBox,
    QPlainTextEdit, QStackedWidget, QSlider, QDialogButtonBox,
)

from . import theme
from ..engines import OPENAI_PRESETS, CLAUDE_MODELS
from ..i18n import t
from ..ocr import win_ocr_install_hint


def _hint(text: str) -> QLabel:
    l = QLabel(text)
    l.setObjectName("hint")
    l.setWordWrap(True)
    return l


def _secret(value: str) -> QLineEdit:
    e = QLineEdit(value)
    e.setEchoMode(QLineEdit.Password)
    return e


def _form(w: QWidget) -> QFormLayout:
    f = QFormLayout(w)
    f.setContentsMargins(16, 16, 16, 16)
    f.setVerticalSpacing(10)
    f.setHorizontalSpacing(14)
    return f


class _Async(QObject):
    done = Signal(object, object)  # (label, (ok, payload))


class SettingsDialog(QDialog):
    def __init__(self, cfg: dict, engines: dict, reader, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("Settings") + " · SubLens")
        self.resize(620, 660)
        self.cfg = copy.deepcopy(cfg)
        self.engines = engines
        self.reader = reader
        self._async = _Async()
        self._async.done.connect(self._on_async)

        tabs = QTabWidget()
        tabs.addTab(self._translation_tab(), t("Translation"))
        tabs.addTab(self._reading_tab(), t("Screen reading"))
        tabs.addTab(self._overlay_tab(), t("Overlay"))
        tabs.addTab(self._general_tab(), t("General"))

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Save).setText(t("Save"))
        bb.button(QDialogButtonBox.Save).setObjectName("primary")
        bb.button(QDialogButtonBox.Cancel).setText(t("Cancel"))
        bb.accepted.connect(self._accept)
        bb.rejected.connect(self.reject)

        v = QVBoxLayout(self)
        v.setContentsMargins(16, 16, 16, 12)
        v.addWidget(tabs, 1)
        v.addWidget(bb)

    # -- helpers ------------------------------------------------------------------
    def _run_async(self, label: QLabel, fn):
        label.setText(t("Working..."))
        label.setStyleSheet(f"color: {theme.WARN};")

        def run():
            try:
                self._async.done.emit(label, (True, fn()))
            except Exception as e:
                self._async.done.emit(label, (False, e))
        threading.Thread(target=run, daemon=True).start()

    def _on_async(self, label, result):
        ok, payload = result
        try:
            if callable(getattr(label, "on_result", None)) and ok:
                payload = label.on_result(payload)
            label.setText(str(payload))
            label.setStyleSheet(f"color: {theme.OK if ok else theme.ERR};")
        except RuntimeError:
            pass  # dialog closed meanwhile

    # -- Translation ----------------------------------------------------------------
    def _translation_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 16, 16, 16)
        e = self.cfg["engines"]

        row = QHBoxLayout()
        row.addWidget(QLabel(t("Configure:")))
        self.eng_pick = QComboBox()
        for key, eng in self.engines.items():
            if key == "none":           # nothing to configure
                continue
            self.eng_pick.addItem(theme.dot_icon(theme.ENGINE_COLOR.get(key, theme.DIM)),
                                  t(eng.name), key)
        row.addWidget(self.eng_pick, 1)
        v.addLayout(row)

        self.stack = QStackedWidget()
        v.addWidget(self.stack)

        # Google
        g = QWidget(); f = QFormLayout(g)
        f.addRow(_hint(t("No setup needed. It uses Google's free web endpoint, which can "
                         "occasionally rate-limit heavy use - switch engine for a while if it does.")))
        self._add_test_row(f, "google", lambda: None)
        self.stack.addWidget(g)

        # DeepL
        g = QWidget(); f = QFormLayout(g)
        self.deepl_key = _secret(e["deepl"].get("api_key", ""))
        f.addRow(t("API key"), self.deepl_key)
        f.addRow(_hint(t("deepl.com > API > 'DeepL API Free' (500,000 characters/month). "
                         "Free keys end with ':fx'. Previous lines are sent as context.")))
        self._add_test_row(f, "deepl", lambda: {"api_key": self.deepl_key.text()})
        self.stack.addWidget(g)

        # OpenAI-compatible
        g = QWidget(); f = QFormLayout(g)
        oa = e["openai"]
        self.oa_preset = QComboBox()
        self.oa_preset.addItems(list(OPENAI_PRESETS))
        self.oa_preset.setCurrentText(oa.get("preset", "LM Studio"))
        self.oa_url = QLineEdit(oa.get("base_url", ""))
        self.oa_key = _secret(oa.get("api_key", ""))
        self.oa_model = QComboBox(); self.oa_model.setEditable(True)
        if oa.get("model"):
            self.oa_model.addItem(oa["model"])
        self.oa_model.setCurrentText(oa.get("model", ""))
        self.oa_model.lineEdit().setPlaceholderText(t("empty = first loaded model"))
        self.oa_preset.currentTextChanged.connect(
            lambda p: OPENAI_PRESETS.get(p) and self.oa_url.setText(OPENAI_PRESETS[p]))
        f.addRow(t("Service"), self.oa_preset)
        f.addRow(t("Base URL"), self.oa_url)
        f.addRow(t("API key"), self.oa_key)
        f.addRow(t("Model"), self.oa_model)
        f.addRow(_hint(t("LM Studio: load a model and start the local server. Ollama: run "
                         "'ollama serve'. Cloud services need an API key. Local models are "
                         "offline and private but use GPU/RAM next to the game.")))
        self._add_test_row(f, "openai", lambda: {
            "base_url": self.oa_url.text(), "api_key": self.oa_key.text(),
            "model": self.oa_model.currentText()}, models_combo=self.oa_model)
        self.stack.addWidget(g)

        # Claude
        g = QWidget(); f = QFormLayout(g)
        cl = e["claude"]
        self.cl_key = _secret(cl.get("api_key", ""))
        self.cl_model = QComboBox(); self.cl_model.setEditable(True)
        self.cl_model.addItems(CLAUDE_MODELS)
        self.cl_model.setCurrentText(cl.get("model", CLAUDE_MODELS[0]))
        f.addRow(t("API key"), self.cl_key)
        f.addRow(t("Model"), self.cl_model)
        f.addRow(_hint(t("Key from console.anthropic.com (empty = ANTHROPIC_API_KEY). "
                         "Opus gives the best translations; Haiku is much faster and cheaper "
                         "for fast-paced dialogue.")))
        self._add_test_row(f, "claude", lambda: {"api_key": self.cl_key.text(),
                                                 "model": self.cl_model.currentText()})
        self.stack.addWidget(g)

        # Gemini
        g = QWidget(); f = QFormLayout(g)
        ge = e["gemini"]
        self.ge_key = _secret(ge.get("api_key", ""))
        self.ge_model = QComboBox(); self.ge_model.setEditable(True)
        self.ge_model.addItem(ge.get("model", "gemini-2.5-flash"))
        f.addRow(t("API key"), self.ge_key)
        f.addRow(t("Model"), self.ge_model)
        f.addRow(_hint(t("Key from aistudio.google.com. 'Test' lists the models your key can use.")))
        self._add_test_row(f, "gemini", lambda: {"api_key": self.ge_key.text(),
                                                 "model": self.ge_model.currentText()},
                           models_combo=self.ge_model)
        self.stack.addWidget(g)

        self.eng_pick.currentIndexChanged.connect(self.stack.setCurrentIndex)
        idx = max(0, self.eng_pick.findData(self.cfg["engine"]))
        self.eng_pick.setCurrentIndex(idx)
        self.stack.setCurrentIndex(idx)

        v.addSpacing(8)
        v.addWidget(QLabel(t("Game context (AI engines)")))
        self.ctx = QLineEdit(self.cfg.get("ctx", ""))
        self.ctx.setPlaceholderText(t("e.g. Red Dead Redemption 2 - Wild West 1899, outlaw gang slang"))
        v.addWidget(self.ctx)
        v.addWidget(QLabel(t("Glossary")))
        v.addWidget(_hint(t("One per line. 'Dutch' keeps the word untranslated, "
                            "'Saint Denis=Saint-Denis' forces a rendering. # starts a comment.")))
        self.glossary = QPlainTextEdit(self.cfg.get("glossary", ""))
        self.glossary.setPlaceholderText("Arthur\nDutch\nVan der Linde\nSpider-Man=Örümcek Adam")
        v.addWidget(self.glossary, 1)
        return w

    def _add_test_row(self, form: QFormLayout, key: str, values, models_combo=None):
        btn = QPushButton(t("Test"))
        status = QLabel("")
        status.setWordWrap(True)
        row = QHBoxLayout()
        row.addWidget(btn)
        row.addWidget(status, 1)
        form.addRow(row)
        eng = self.engines[key]

        if models_combo is not None:
            def fill(models_msg):
                models, msg = models_msg
                cur = models_combo.currentText()
                models_combo.clear()
                models_combo.addItems(models)
                models_combo.setCurrentText(cur if cur else (models[0] if models else ""))
                return msg
            status.on_result = fill

        def run():
            cfg = values() or {}
            eng.configure(cfg)
            msg = eng.test()
            if models_combo is not None:
                return (eng.models(), msg)
            return msg
        btn.clicked.connect(lambda: self._run_async(status, run))

    # -- Reading --------------------------------------------------------------------
    def _reading_tab(self):
        w = QWidget()
        f = _form(w)
        win = self.reader.windows
        if win.available:
            langs = ", ".join(win.languages()) or "-"
            f.addRow(_hint(t("Text is read with Windows OCR. Installed languages: {}. "
                             "Add more under Windows Settings > Time & language > Language "
                             "(tick 'Optical character recognition').", langs)))
            src = self.cfg.get("src_lang", "English")
            if not win.supports(src):
                warn = _hint(win_ocr_install_hint(src))
                warn.setStyleSheet(f"color: {theme.WARN};")
                warn.setTextInteractionFlags(Qt.TextSelectableByMouse)
                f.addRow(warn)
        else:
            f.addRow(_hint(t("Windows OCR is unavailable (needs Windows 10/11 and the "
                             "winrt packages from requirements.txt).")))

        self.scale = QComboBox()
        self.scale.addItem(t("Automatic"), 0)
        for s in (1, 2, 3, 4):
            self.scale.addItem(f"{s}x", s)
        self.scale.setCurrentIndex(max(0, self.scale.findData(int(self.cfg.get("ocr_scale", 0)))))
        f.addRow(t("Upscale"), self.scale)

        self.interval = QDoubleSpinBox()
        self.interval.setRange(0.1, 5.0); self.interval.setSingleStep(0.05)
        self.interval.setSuffix(" s"); self.interval.setValue(float(self.cfg.get("interval", 0.25)))
        f.addRow(t("Read every"), self.interval)
        f.addRow(_hint(t("The area is only OCR'd when its pixels change, so short intervals are cheap.")))

        self.wait_stable = QCheckBox(t("Wait until the text stops changing before translating"))
        self.wait_stable.setChecked(bool(self.cfg.get("wait_stable", True)))
        f.addRow(self.wait_stable)
        f.addRow(_hint(t("Avoids translating half-faded or typewriter text. Adds one read of delay.")))

        self.ctx_lines = QSpinBox(); self.ctx_lines.setRange(0, 12)
        self.ctx_lines.setValue(int(self.cfg.get("context_lines", 6)))
        f.addRow(t("Context lines"), self.ctx_lines)
        f.addRow(_hint(t("Previous lines sent along (AI engines and DeepL) for consistent "
                         "pronouns, gender and tone.")))
        return w

    # -- Overlay --------------------------------------------------------------------
    def _overlay_tab(self):
        w = QWidget()
        f = _form(w)
        self.ov_show = QCheckBox(t("Show translations over the game"))
        self.ov_show.setChecked(bool(self.cfg.get("show_overlay", True)))
        f.addRow(self.ov_show)
        self.ov_font = QSpinBox(); self.ov_font.setRange(9, 40); self.ov_font.setSuffix(" pt")
        self.ov_font.setValue(int(self.cfg.get("overlay_font", 15)))
        f.addRow(t("Font size"), self.ov_font)
        self.ov_opacity = QSlider(Qt.Horizontal); self.ov_opacity.setRange(20, 100)
        self.ov_opacity.setValue(int(float(self.cfg.get("overlay_opacity", 0.88)) * 100))
        f.addRow(t("Background"), self.ov_opacity)
        self.ov_pos = QComboBox()
        for k, label in (("above", "Above the subtitle area"), ("below", "Below the subtitle area"),
                         ("fixed", "Where I drag it")):
            self.ov_pos.addItem(t(label), k)
        self.ov_pos.setCurrentIndex(max(0, self.ov_pos.findData(self.cfg.get("overlay_position"))))
        f.addRow(t("Position"), self.ov_pos)
        self.ov_orig = QCheckBox(t("Also show the original text (small)"))
        self.ov_orig.setChecked(bool(self.cfg.get("overlay_show_original")))
        f.addRow(self.ov_orig)
        self.ov_ct = QCheckBox(t("Click-through (mouse goes to the game; can't be dragged)"))
        self.ov_ct.setChecked(bool(self.cfg.get("overlay_click_through")))
        f.addRow(self.ov_ct)
        self.ov_hide = QDoubleSpinBox(); self.ov_hide.setRange(0, 30); self.ov_hide.setSuffix(" s")
        self.ov_hide.setValue(float(self.cfg.get("overlay_hide_after", 2.0)))
        f.addRow(t("Hide after subtitle ends"), self.ov_hide)
        f.addRow(_hint(t("0 = keep the last translation on screen. Drag the overlay to move it; "
                         "right-click hides it.")))
        return w

    # -- General --------------------------------------------------------------------
    def _general_tab(self):
        w = QWidget()
        f = _form(w)
        self.ui_lang = QComboBox()
        self.ui_lang.addItem(t("Same as Windows"), "")
        self.ui_lang.addItem("English", "en")
        self.ui_lang.addItem("Türkçe", "tr")
        self.ui_lang.setCurrentIndex(max(0, self.ui_lang.findData(self.cfg.get("ui_lang", ""))))
        f.addRow(t("Interface language"), self.ui_lang)
        self.hotkeys = QCheckBox(t("Global shortcuts (work while the game is focused)"))
        self.hotkeys.setChecked(bool(self.cfg.get("global_hotkeys", True)))
        f.addRow(self.hotkeys)
        f.addRow(_hint(t("F2 / Ctrl+Alt+R  select area   ·   F3 / Ctrl+Alt+T  translate once\n"
                         "F4 / Ctrl+Alt+G  start/stop   ·   Ctrl+Alt+H  hide overlay\n"
                         "Some games run as administrator - then SubLens must too.")))
        self.auto_pause = QCheckBox(t("Pause reading while the game is not the active window"))
        self.auto_pause.setChecked(bool(self.cfg.get("auto_pause", True)))
        f.addRow(self.auto_pause)
        self.tray = QCheckBox(t("Closing the window keeps SubLens in the tray"))
        self.tray.setChecked(bool(self.cfg.get("minimize_to_tray", True)))
        f.addRow(self.tray)
        self.notify = QCheckBox(t("Show Windows notifications"))
        self.notify.setChecked(bool(self.cfg.get("notifications", True)))
        f.addRow(self.notify)
        self.updates = QCheckBox(t("Check for new versions at startup"))
        self.updates.setChecked(bool(self.cfg.get("check_updates", True)))
        f.addRow(self.updates)
        return w

    # -- save -------------------------------------------------------------------------
    def _accept(self):
        c = self.cfg
        e = c["engines"]
        e["deepl"]["api_key"] = self.deepl_key.text().strip()
        e["openai"].update(preset=self.oa_preset.currentText(), base_url=self.oa_url.text().strip(),
                           api_key=self.oa_key.text().strip(),
                           model=self.oa_model.currentText().strip())
        e["claude"].update(api_key=self.cl_key.text().strip(),
                           model=self.cl_model.currentText().strip())
        e["gemini"].update(api_key=self.ge_key.text().strip(),
                           model=self.ge_model.currentText().strip())
        c["ctx"] = self.ctx.text().strip()
        c["glossary"] = self.glossary.toPlainText()
        c["ocr_scale"] = int(self.scale.currentData())
        c["interval"] = float(self.interval.value())
        c["wait_stable"] = self.wait_stable.isChecked()
        c["context_lines"] = int(self.ctx_lines.value())
        c["show_overlay"] = self.ov_show.isChecked()
        c["overlay_font"] = int(self.ov_font.value())
        c["overlay_opacity"] = self.ov_opacity.value() / 100
        c["overlay_position"] = self.ov_pos.currentData()
        c["overlay_show_original"] = self.ov_orig.isChecked()
        c["overlay_click_through"] = self.ov_ct.isChecked()
        c["overlay_hide_after"] = float(self.ov_hide.value())
        c["ui_lang"] = self.ui_lang.currentData()
        c["global_hotkeys"] = self.hotkeys.isChecked()
        c["auto_pause"] = self.auto_pause.isChecked()
        c["minimize_to_tray"] = self.tray.isChecked()
        c["notifications"] = self.notify.isChecked()
        c["check_updates"] = self.updates.isChecked()
        self.accept()
