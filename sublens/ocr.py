"""OCR and image preparation.

Windows OCR (Windows.Media.Ocr) ships with Windows 10/11, reads stylised game
fonts far better than Tesseract did in v1 and takes ~10-30 ms per frame.
"""
from __future__ import annotations

import asyncio
import threading

import numpy as np
from PIL import Image, ImageFilter, ImageOps

from .i18n import t
from .textproc import Word, Line, clean_lines, lines_to_text, text_score

# -----------------------------------------------------------------------------
#  Language tables
# -----------------------------------------------------------------------------

WIN_LANG = {
    "English": "en", "Turkish": "tr", "Japanese": "ja", "Korean": "ko",
    "Chinese": "zh-Hans", "French": "fr", "German": "de", "Spanish": "es",
    "Russian": "ru", "Italian": "it", "Portuguese": "pt", "Polish": "pl",
}
WIN_CAPABILITY = {  # names for Add-WindowsCapability
    "English": "en-US", "Turkish": "tr-TR", "Japanese": "ja-JP", "Korean": "ko-KR",
    "Chinese": "zh-CN", "French": "fr-FR", "German": "de-DE", "Spanish": "es-ES",
    "Russian": "ru-RU", "Italian": "it-IT", "Portuguese": "pt-PT", "Polish": "pl-PL",
}
TEXT_STYLES = [
    ("auto", "Tries the raw frame and the bright-subtitle filter, keeps the cleaner text."),
    ("subtitle", "White / outlined / shadowed subtitles over busy scenes."),
    ("plain", "Dialog boxes and menus on a flat background."),
]


def win_ocr_install_hint(lang: str) -> str:
    cap = WIN_CAPABILITY.get(lang, "en-US")
    return t("Windows OCR has no '{}' language pack. Install it from Settings > Time & "
             "language > Language > Add a language (tick 'Optical character recognition'), "
             "or in an admin PowerShell:  Add-WindowsCapability -Online -Name "
             "\"Language.OCR~~~{}~0.0.1.0\"", t(lang), cap)


# -----------------------------------------------------------------------------
#  Image preparation
# -----------------------------------------------------------------------------

def isolate_bright_text(img: Image.Image, scale: int = 1) -> Image.Image:
    """Keep bright, unsaturated pixels that sit next to a darker edge.

    Game subtitles are white(ish) with an outline, drop shadow or dim backing.
    Requiring a darker pixel nearby separates glyph strokes from large bright
    areas (sky, snow, lamps) that would otherwise turn into solid blobs.
    Output: black text on white, which every OCR engine likes.
    """
    a = np.asarray(img.convert("RGB"), dtype=np.int32)
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    lum = (a[..., 0] * 299 + a[..., 1] * 587 + a[..., 2] * 114) // 1000

    # brightness threshold adapts to the brightest text in the frame
    hi = float(np.percentile(lum, 99.5))
    thr = max(150.0, min(215.0, hi - 45))
    bright = (lum >= thr) & ((mx - mn) <= 70)

    # darker surroundings within a few pixels (outline, shadow, backing box)
    gray = Image.fromarray(lum.clip(0, 255).astype(np.uint8))
    # window must reach past a glyph stroke to its outline; strokes grow with upscaling
    k = 3 + 2 * max(1, scale)
    local_min = np.asarray(gray.filter(ImageFilter.MinFilter(k)), dtype=np.int32)
    edge = (lum - local_min) >= 70

    mask = bright & edge
    # close tiny holes inside glyphs
    m = Image.fromarray(np.where(mask, 255, 0).astype(np.uint8))
    m = m.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    return ImageOps.invert(m).convert("RGB")


def enhance_plain(img: Image.Image) -> Image.Image:
    g = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    return g.convert("RGB")


def prepare(img: Image.Image, style: str, scale: int) -> Image.Image:
    if scale > 1:
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
    if style == "subtitle":
        return isolate_bright_text(img, scale)
    if style == "plain":
        return enhance_plain(img)
    return img


def auto_scale(img: Image.Image) -> int:
    """Windows OCR wants glyphs ~20-40 px tall. Small regions get upscaled."""
    h = img.height
    if h < 70:
        return 3
    if h < 160:
        return 2
    return 1


# -----------------------------------------------------------------------------
#  Backends
# -----------------------------------------------------------------------------

class OcrError(Exception):
    pass


class WindowsOcr:
    name = "Windows OCR"
    key = "windows"

    def __init__(self):
        self._local = threading.local()
        self._engines: dict[str, object] = {}
        self._lock = threading.Lock()
        try:
            from winrt.windows.media.ocr import OcrEngine  # noqa: F401
            self.available = True
        except Exception:
            self.available = False

    def languages(self) -> list[str]:
        if not self.available:
            return []
        from winrt.windows.media.ocr import OcrEngine
        return [l.language_tag for l in OcrEngine.available_recognizer_languages]

    def supports(self, lang: str) -> bool:
        if lang == "Auto-Detect":
            return self.available
        tag = WIN_LANG.get(lang)
        return bool(tag) and any(t.lower().startswith(tag.lower().split("-")[0])
                                 for t in self.languages())

    def _engine(self, lang: str):
        with self._lock:
            if lang in self._engines:
                return self._engines[lang]
            from winrt.windows.media.ocr import OcrEngine
            from winrt.windows.globalization import Language
            eng = None
            if lang == "Auto-Detect":
                eng = OcrEngine.try_create_from_user_profile_languages()
            else:
                want = WIN_LANG.get(lang, "en").lower()
                for t in self.languages():
                    tl = t.lower()
                    if tl == want or tl.startswith(want.split("-")[0]):
                        eng = OcrEngine.try_create_from_language(Language(t))
                        break
            if eng is None:
                raise OcrError(win_ocr_install_hint(lang))
            self._engines[lang] = eng
            return eng

    def _loop(self):
        loop = getattr(self._local, "loop", None)
        if loop is None:
            loop = asyncio.new_event_loop()
            self._local.loop = loop
        return loop

    def read(self, img: Image.Image, lang: str) -> list[Line]:
        from winrt.windows.graphics.imaging import (
            SoftwareBitmap, BitmapPixelFormat, BitmapAlphaMode)
        from winrt.windows.storage.streams import DataWriter

        eng = self._engine(lang)
        rgba = img.convert("RGBA")
        writer = DataWriter()
        writer.write_bytes(rgba.tobytes())
        bmp = SoftwareBitmap.create_copy_from_buffer(
            writer.detach_buffer(), BitmapPixelFormat.RGBA8,
            rgba.width, rgba.height, BitmapAlphaMode.STRAIGHT)
        res = self._loop().run_until_complete(eng.recognize_async(bmp))
        lines: list[Line] = []
        for ln in res.lines:
            words = []
            for w in ln.words:
                r = w.bounding_rect
                words.append(Word(w.text, r.x, r.y, r.width, r.height))
            if words:
                lines.append(words)
        return lines


# -----------------------------------------------------------------------------
#  Facade
# -----------------------------------------------------------------------------

class OcrResult:
    __slots__ = ("text", "lines", "processed", "backend")

    def __init__(self, text: str, lines: list[Line], processed: Image.Image, backend: str):
        self.text = text
        self.lines = lines
        self.processed = processed
        self.backend = backend

    def box(self) -> tuple[int, int, int, int] | None:
        """Bounding box of the kept text, in pixels relative to the captured area."""
        words = [w for l in self.lines for w in l]
        if not words:
            return None
        return (int(min(w.x for w in words)), int(min(w.y for w in words)),
                int(max(w.right for w in words)), int(max(w.y + w.h for w in words)))


class Reader:
    """Runs Windows OCR with the user's style/scale settings and cleans the result."""

    def __init__(self):
        self.windows = WindowsOcr()

    def check(self, lang: str):
        """Raises OcrError with a fix-it message when `lang` can't be read."""
        if not self.windows.available:
            raise OcrError(t("Windows OCR is unavailable (needs Windows 10/11 and the "
                             "winrt packages from requirements.txt)."))
        if not self.windows.supports(lang):
            raise OcrError(win_ocr_install_hint(lang))
        return self.windows

    def read(self, img: Image.Image, lang: str, style: str = "auto",
             scale: int = 0) -> OcrResult:
        be = self.check(lang)
        s = scale or auto_scale(img)
        if style == "auto":
            # busy backgrounds defeat the raw frame, flat ones can trip the filter:
            # read both (Windows OCR is cheap) and keep whichever looks like language
            best = None
            for st in ("auto", "subtitle"):
                proc = prepare(img, st, s)
                res = self._finish(be.read(proc, lang), s, proc, be.key)
                score = text_score(res.text)
                if best is None or score > best[0]:
                    best = (score, res)
            return best[1]
        proc = prepare(img, style, s)
        return self._finish(be.read(proc, lang), s, proc, be.key)

    @staticmethod
    def _finish(raw: list[Line], s: int, proc, backend: str) -> OcrResult:
        if s > 1:
            raw = [[Word(w.text, w.x / s, w.y / s, w.w / s, w.h / s) for w in l] for l in raw]
        lines = clean_lines(raw)
        return OcrResult(lines_to_text(lines), lines, proc, backend)
