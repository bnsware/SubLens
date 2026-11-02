"""Claude via the official Anthropic SDK (pip install anthropic)."""
from __future__ import annotations

from ..i18n import t

from .base import Request, EngineError, build_llm_prompt, clean_llm_output

MODELS = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"]
# Models that accept the server-side refusal fallback
_FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class ClaudeEngine:
    key = "claude"
    name = "Claude"
    note = "Anthropic API key. Haiku is the fastest/cheapest for live subtitles."
    is_llm = True

    def __init__(self):
        self.api_key = ""
        self.model = MODELS[0]
        self._client = None
        self._client_key = None

    def configure(self, cfg: dict):
        self.api_key = (cfg.get("api_key") or "").strip()
        self.model = (cfg.get("model") or MODELS[0]).strip()

    def _get_client(self):
        try:
            import anthropic
        except ImportError:
            raise EngineError(t("The 'anthropic' package is missing: pip install anthropic")) from None
        if self._client is None or self._client_key != self.api_key:
            # Empty key -> SDK resolves ANTHROPIC_API_KEY / `ant auth login` itself
            kwargs = {"timeout": 30.0, "max_retries": 2}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            self._client = anthropic.Anthropic(**kwargs)
            self._client_key = self.api_key
        return self._client

    def translate(self, req: Request) -> str:
        import anthropic
        client = self._get_client()
        system, turns = build_llm_prompt(req)
        kwargs = dict(
            model=self.model,
            max_tokens=2048,
            system=system,
            messages=[{"role": r, "content": c} for r, c in turns],
            output_config={"effort": "low"},  # short, latency-sensitive task
        )
        if self.model in _FALLBACK_MODELS:
            kwargs.update(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        try:
            resp = client.beta.messages.create(**kwargs)
        except anthropic.AuthenticationError:
            raise EngineError(t("Invalid Anthropic API key")) from None
        except anthropic.NotFoundError:
            raise EngineError(t("Unknown model '{}'", self.model)) from None
        except anthropic.RateLimitError:
            raise EngineError(t("Rate limited by Anthropic - slow down or try later")) from None
        except anthropic.APIStatusError as e:
            raise EngineError(t("Anthropic API error {}: {}", e.status_code, e.message)) from None
        except anthropic.APIConnectionError:
            raise EngineError(t("Could not reach the Anthropic API")) from None
        if resp.stop_reason == "refusal":
            raise EngineError(t("Claude declined to translate this line"))
        text = "".join(b.text for b in resp.content if b.type == "text")
        return clean_llm_output(text)

    def test(self) -> str:
        out = self.translate(Request("Hello there, partner.", "English", "Turkish"))
        return f"{self.model}: '{out}'"
