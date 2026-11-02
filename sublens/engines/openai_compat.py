"""Any OpenAI-compatible chat endpoint: LM Studio, Ollama, OpenAI, OpenRouter, Groq."""
from __future__ import annotations

from ..i18n import t

from .base import Request, EngineError, http_json, build_llm_prompt, clean_llm_output

PRESETS = {
    "LM Studio":  "http://localhost:1234/v1",
    "Ollama":     "http://localhost:11434/v1",
    "OpenAI":     "https://api.openai.com/v1",
    "OpenRouter": "https://openrouter.ai/api/v1",
    "Groq":       "https://api.groq.com/openai/v1",
    "Custom":     "",
}


class OpenAICompatEngine:
    key = "openai"
    name = "AI (OpenAI-compatible)"
    note = "LM Studio / Ollama (local, offline) or OpenAI, OpenRouter, Groq (API key)."
    is_llm = True

    def __init__(self):
        self.base_url = PRESETS["LM Studio"]
        self.api_key = ""
        self.model = ""

    def configure(self, cfg: dict):
        self.base_url = (cfg.get("base_url") or PRESETS["LM Studio"]).rstrip("/")
        self.api_key = (cfg.get("api_key") or "").strip()
        self.model = (cfg.get("model") or "").strip()

    def _headers(self):
        return {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}

    def models(self) -> list[str]:
        data = http_json(f"{self.base_url}/models", headers=self._headers(),
                         timeout=6, method="GET", retries=())
        return sorted(m["id"] for m in data.get("data", []))

    def translate(self, req: Request) -> str:
        if not self.model:
            models = self.models()
            if not models:
                raise EngineError(t("No model loaded on the AI server"))
            self.model = models[0]
        system, turns = build_llm_prompt(req)
        data = http_json(f"{self.base_url}/chat/completions", headers=self._headers(),
                         timeout=45, data={
                             "model": self.model,
                             "messages": [{"role": "system", "content": system}]
                                         + [{"role": r, "content": c} for r, c in turns],
                             "temperature": 0.2,
                             "max_tokens": 600,
                         })
        try:
            return clean_llm_output(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError):
            raise EngineError(t("Unexpected response: {}", str(data)[:200])) from None

    def test(self) -> str:
        models = self.models()
        return t("Connected - {} model(s)", len(models))
