"""Settings: defaults, load/save, legacy migration and per-game profiles."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from . import APP_NAME

_APPDATA = Path(os.environ.get("APPDATA") or Path.home())
APP_DIR = _APPDATA / APP_NAME
CONFIG_PATH = APP_DIR / "config.json"
LEGACY_CONFIG = _APPDATA / "GameTranslator" / "config_qt.json"

LANGS = ["English", "Turkish", "Japanese", "Korean", "Chinese",
         "French", "German", "Spanish", "Russian", "Italian",
         "Portuguese", "Polish"]
SRC_LANGS = LANGS + ["Auto-Detect"]

# Settings that make up a per-game profile (what gets saved / restored)
PROFILE_KEYS = ("region", "src_lang", "text_style", "ocr_scale", "ctx", "glossary")
_OBSOLETE = ("ocr_backend", "tess_mode", "tess_psm")   # Tesseract was removed in 2.1

DEFAULTS: dict = {
    "version": 3,
    "engine": "google",
    "src_lang": "English",
    "tgt_lang": "Turkish",
    "region": None,                 # physical pixels (x1, y1, x2, y2)

    # OCR (Windows OCR)
    "text_style": "auto",           # auto | subtitle | plain
    "ocr_scale": 0,                 # 0 = automatic, else 1..4

    # Scanning
    "interval": 0.25,               # seconds between screen reads
    "wait_stable": True,            # translate only after the text stops changing
    "auto_pause": True,
    "context_lines": 6,             # previous lines (with their translations) sent as context

    # Overlay
    "show_overlay": True,
    "overlay_font": 15,
    "overlay_opacity": 0.88,
    "overlay_position": "above",    # above | below | fixed
    "overlay_xy": None,
    "overlay_show_original": False,
    "overlay_click_through": False,
    "overlay_hide_after": 2.0,      # hide this many seconds after the subtitle disappears (0 = never)

    # Translation
    "ctx": "",
    "glossary": "",
    "engines": {
        "deepl": {"api_key": ""},
        "openai": {"preset": "LM Studio", "base_url": "http://localhost:1234/v1",
                   "api_key": "", "model": ""},
        "claude": {"api_key": "", "model": "claude-opus-5-5"},
        "gemini": {"api_key": "", "model": "gemini-2.5-flash"},
    },

    # App
    "ui_lang": "",                  # "" = follow Windows, else en | tr
    "global_hotkeys": True,
    "minimize_to_tray": True,
    "notifications": True,          # Windows notifications from the tray icon
    "profile": "",
    "profiles": {},                 # name -> {PROFILE_KEYS..., "exe": "game.exe"}
}


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict) and k != "profiles":
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _migrate_v1(old: dict) -> dict:
    """Map a v1 (single-file SubLens / Game Translator) config onto v2 keys."""
    new: dict = {}
    eng = old.get("engine_key")
    new["engine"] = {"lmstudio": "openai"}.get(eng, eng or "google")
    for k in ("src_lang", "tgt_lang", "ctx", "glossary", "auto_pause",
              "minimize_to_tray", "show_overlay"):
        if k in old:
            new[k] = old[k]
    if "global_hotkeys" in old:
        new["global_hotkeys"] = old["global_hotkeys"]
    if isinstance(old.get("region"), list) and len(old["region"]) == 4:
        new["region"] = old["region"]
    new["engines"] = {"deepl": {"api_key": old.get("deepl_key", "")}}
    lm_url = (old.get("lm_url") or "").rstrip("/")
    if lm_url:
        if not lm_url.endswith("/v1"):
            lm_url += "/v1"
        model = old.get("lm_model", "")
        new["engines"]["openai"] = {
            "preset": "LM Studio", "base_url": lm_url, "api_key": "",
            "model": "" if model == "local-model" else model}
    return new


def load() -> dict:
    data = None
    try:
        data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        try:
            data = json.loads(LEGACY_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            data = None
    if not isinstance(data, dict):
        return copy.deepcopy(DEFAULTS)
    if data.get("version", 1) < 2:
        data = _migrate_v1(data)
    if data.get("version", 1) < 3 and data.get("context_lines", 3) == 3:
        data["context_lines"] = 6         # 2.2: context now carries translations, more helps
    cfg = _deep_merge(DEFAULTS, data)
    cfg["version"] = DEFAULTS["version"]
    for k in _OBSOLETE:
        cfg.pop(k, None)
    if cfg["src_lang"] not in SRC_LANGS:
        cfg["src_lang"] = "English"
    if cfg["tgt_lang"] not in LANGS:
        cfg["tgt_lang"] = "Turkish"
    return cfg


def save(cfg: dict) -> None:
    try:
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = CONFIG_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(CONFIG_PATH)
    except Exception:
        pass


def snapshot_profile(cfg: dict, exe: str = "") -> dict:
    prof = {k: copy.deepcopy(cfg.get(k)) for k in PROFILE_KEYS}
    prof["exe"] = exe
    return prof


def apply_profile(cfg: dict, prof: dict) -> None:
    for k in PROFILE_KEYS:
        if k in prof:
            cfg[k] = copy.deepcopy(prof[k])


def profile_for_exe(cfg: dict, exe: str) -> str | None:
    exe = (exe or "").lower()
    if not exe:
        return None
    for name, prof in cfg.get("profiles", {}).items():
        if (prof.get("exe") or "").lower() == exe:
            return name
    return None
