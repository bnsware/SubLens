"""Translation engines. Each has key/name/note/is_llm, configure(), translate(), test()."""
from __future__ import annotations

from .base import Request, EngineError
from .google import GoogleEngine
from .deepl import DeepLEngine
from .openai_compat import OpenAICompatEngine, PRESETS as OPENAI_PRESETS
from .claude import ClaudeEngine, MODELS as CLAUDE_MODELS
from .gemini import GeminiEngine
from .none import NoTranslation


def create_all() -> dict:
    return {e.key: e for e in (GoogleEngine(), DeepLEngine(), OpenAICompatEngine(),
                               ClaudeEngine(), GeminiEngine(), NoTranslation())}


__all__ = ["Request", "EngineError", "create_all", "OPENAI_PRESETS", "CLAUDE_MODELS"]
