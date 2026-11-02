"""Google Gemini (generativelanguage REST API, API key from aistudio.google.com)."""
from __future__ import annotations

from ..i18n import t

from .base import Request, EngineError, http_json, build_llm_prompt, clean_llm_output

API = "https://generativelanguage.googleapis.com/v1beta"


class GeminiEngine:
    key = "gemini"
    name = "Gemini"
    note = "Google AI Studio API key (has a free tier)."
    is_llm = True

    def __init__(self):
        self.api_key = ""
        self.model = "gemini-2.5-flash"

    def configure(self, cfg: dict):
        self.api_key = (cfg.get("api_key") or "").strip()
        self.model = (cfg.get("model") or "gemini-2.5-flash").strip().removeprefix("models/")

    def _headers(self):
        if not self.api_key:
            raise EngineError(t("Gemini API key is empty (Settings > Translation)"))
        return {"x-goog-api-key": self.api_key}

    def models(self) -> list[str]:
        data = http_json(f"{API}/models?pageSize=200", headers=self._headers(),
                         timeout=8, method="GET", retries=())
        return sorted(m["name"].removeprefix("models/") for m in data.get("models", [])
                      if "generateContent" in m.get("supportedGenerationMethods", []))

    def translate(self, req: Request) -> str:
        system, turns = build_llm_prompt(req)
        data = http_json(f"{API}/models/{self.model}:generateContent",
                         headers=self._headers(), timeout=30, data={
                             "systemInstruction": {"parts": [{"text": system}]},
                             "contents": [{"role": "model" if r == "assistant" else "user",
                                           "parts": [{"text": c}]} for r, c in turns],
                             "generationConfig": {"temperature": 0.2, "maxOutputTokens": 800},
                         })
        try:
            parts = data["candidates"][0]["content"]["parts"]
            return clean_llm_output("".join(p.get("text", "") for p in parts))
        except (KeyError, IndexError):
            reason = (data.get("promptFeedback") or {}).get("blockReason")
            raise EngineError(t("Gemini returned no text") + (f" ({reason})" if reason else "")) from None

    def test(self) -> str:
        models = self.models()
        if self.model not in models:
            return t("Key OK, but '{}' not found. Available: {}", self.model, ", ".join(models[:6]))
        return t("Key OK - {} available", self.model)
