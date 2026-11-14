from __future__ import annotations

from .base import Request


class NoTranslation:
    """Shows the text as read. For reading small or blurry game text, and works offline."""
    key = "none"
    name = "No translation (text only)"
    note = ("Shows the text as it is read, without translating. Works offline - "
            "handy for small or hard-to-read text.")
    is_llm = False

    def configure(self, cfg: dict):
        pass

    def translate(self, req: Request) -> str:
        return req.text

    def test(self) -> str:
        return "OK"
