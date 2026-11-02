from __future__ import annotations

from ..i18n import t

import urllib.parse

from .base import Request, EngineError, http_json


class GoogleEngine:
    key = "google"
    name = "Google Translate"
    note = "Free, no key. Unofficial endpoint - Google may rate-limit it."
    is_llm = False

    LANG = {"Turkish": "tr", "English": "en", "Japanese": "ja", "Korean": "ko",
            "Chinese": "zh-CN", "French": "fr", "German": "de", "Spanish": "es",
            "Russian": "ru", "Italian": "it", "Portuguese": "pt", "Polish": "pl",
            "Auto-Detect": "auto"}

    def configure(self, cfg: dict):
        pass

    def translate(self, req: Request) -> str:
        sl = self.LANG.get(req.src, "auto")
        tl = self.LANG.get(req.tgt, "tr")
        url = ("https://translate.googleapis.com/translate_a/single?client=gtx&dt=t"
               f"&sl={sl}&tl={tl}")
        data = http_json(url, form={"q": req.text}, timeout=10, method="POST")
        try:
            return "".join(seg[0] for seg in data[0] if seg and seg[0]).strip()
        except Exception:
            raise EngineError(t("Unexpected response from Google")) from None

    def test(self) -> str:
        out = self.translate(Request("Hello world", "English", "Turkish"))
        if not out:
            raise EngineError(t("Empty response"))
        return f"'Hello world' -> '{out}'"
