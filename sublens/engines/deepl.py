from __future__ import annotations

from ..i18n import t

from .base import Request, EngineError, http_json


class DeepLEngine:
    key = "deepl"
    name = "DeepL"
    note = "Best quality machine translation. Free plan: 500k characters / month."
    is_llm = False

    TGT = {"Turkish": "TR", "English": "EN-US", "Japanese": "JA", "Korean": "KO",
           "Chinese": "ZH-HANS", "French": "FR", "German": "DE", "Spanish": "ES",
           "Russian": "RU", "Italian": "IT", "Portuguese": "PT-BR", "Polish": "PL"}

    def __init__(self):
        self.api_key = ""

    def configure(self, cfg: dict):
        self.api_key = (cfg.get("api_key") or "").strip()

    @property
    def _base(self) -> str:
        # Free-plan keys end with ":fx"
        return ("https://api-free.deepl.com" if self.api_key.endswith(":fx")
                else "https://api.deepl.com")

    def _headers(self):
        if not self.api_key:
            raise EngineError(t("DeepL API key is empty (Settings > Translation)"))
        return {"Authorization": f"DeepL-Auth-Key {self.api_key}"}

    def translate(self, req: Request) -> str:
        body = {"text": [req.text], "target_lang": self.TGT.get(req.tgt, "EN-US"),
                "preserve_formatting": True}
        if req.src in self.TGT:
            body["source_lang"] = self.TGT[req.src].split("-")[0]
        if req.history:
            # DeepL uses this to resolve pronouns/gender, it is not translated or billed
            body["context"] = "\n".join(src for src, _ in req.history)
        data = http_json(f"{self._base}/v2/translate", data=body,
                         headers=self._headers(), timeout=15)
        return data["translations"][0]["text"]

    def test(self) -> str:
        u = http_json(f"{self._base}/v2/usage", headers=self._headers(), timeout=10,
                      method="GET")
        return t("{:,} / {:,} characters used", u['character_count'], u['character_limit'])
