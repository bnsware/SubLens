"""Shared engine pieces: request context, HTTP helper, LLM prompt."""
from __future__ import annotations

from ..i18n import t

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 Chrome/130.0 Safari/537.36")


@dataclass
class Request:
    text: str
    src: str
    tgt: str
    game_ctx: str = ""
    # the conversation so far, oldest first: (source line, our translation of it)
    history: list[tuple[str, str]] = field(default_factory=list)
    glossary: list[tuple[str, str]] = field(default_factory=list)


class EngineError(Exception):
    pass


def http_json(url: str, *, data: dict | None = None, form: dict | None = None,
              headers: dict | None = None, timeout: float = 20, method: str | None = None,
              retries: tuple = (1, 3)) -> dict:
    hdrs = {"User-Agent": USER_AGENT}
    hdrs.update(headers or {})
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        hdrs["Content-Type"] = "application/json"
    elif form is not None:
        body = urllib.parse.urlencode(form, doseq=True).encode()
        hdrs["Content-Type"] = "application/x-www-form-urlencoded"
    delays = list(retries) + [None]
    for delay in delays:
        req = urllib.request.Request(url, data=body, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and delay is not None:
                time.sleep(delay)
                continue
            detail = ""
            try:
                detail = e.read().decode("utf-8", "replace")
                j = json.loads(detail)
                err = j.get("error", j) if isinstance(j, dict) else {}
                detail = (err.get("message") if isinstance(err, dict) else str(err)) or detail
            except Exception:
                pass
            detail = " ".join(str(detail).split())[:200]
            raise EngineError(f"HTTP {e.code}: {detail or e.reason}") from None
        except urllib.error.URLError as e:
            raise EngineError(t("Connection failed: {}", e.reason)) from None
    raise EngineError(t("Request failed"))


def build_llm_prompt(req: Request) -> tuple[str, list[tuple[str, str]]]:
    """System prompt + chat turns [(role, content)] shared by every LLM engine.

    Earlier lines are replayed as real user/assistant turns (source, our
    translation). The model then sees the new line as the next line of the same
    conversation - that is what lets it render "Neyi?" after "You should try
    this." as "Try what?" instead of a context-free "What?".
    """
    system = (
        f"You are a professional video game localizer translating on-screen subtitles "
        f"and dialogue from {req.src if req.src != 'Auto-Detect' else 'the source language'} "
        f"into {req.tgt}, live, one line at a time.\n"
        "- Output only the translation of the text inside <text>, with no quotes, notes, "
        "labels or explanations.\n"
        "- The lines are consecutive subtitles of one ongoing conversation or scene. "
        "Translate each new line as the next line of that conversation, the way a native "
        "speaker would say it at that point. Short replies, questions and fragments only make "
        "sense with what came before - e.g. after \"You should try this.\", Turkish \"Neyi?\" "
        "is \"Try what?\", not \"What?\". Use the earlier lines to pick pronouns, gender, "
        "formality, tense and terminology, and keep them consistent with your earlier "
        "translations. Never repeat or re-translate earlier lines.\n"
        "- A line may be a piece of a sentence that continues in the next subtitle; translate "
        "it so it flows on from the previous one.\n"
        "- Sound natural, like an official localization: keep the tone, slang and register "
        "of the speaker, keep it about as short as the original.\n"
        "- Keep speaker tags such as 'MILES:' and proper names unchanged unless the glossary "
        "says otherwise. Keep one output line per input line.\n"
        "- The text comes from OCR and can contain small recognition errors; quietly fix "
        "obvious ones instead of translating them literally.\n"
        "- If the text is not language (a stray symbol or button label), return it unchanged."
    )
    if req.game_ctx:
        system += f"\n\nGame / setting: {req.game_ctx}"
    if req.glossary:
        system += "\n\nGlossary (always use these renderings):\n" + "\n".join(
            f"{s} -> {t}" for s, t in req.glossary)
    turns: list[tuple[str, str]] = []
    for src, out in req.history:
        turns += [("user", f"<text>\n{src}\n</text>"), ("assistant", out)]
    turns.append(("user", f"<text>\n{req.text}\n</text>"))
    return system, turns


_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


def clean_llm_output(s: str) -> str:
    s = _THINK_RE.sub("", s or "").strip()
    s = re.sub(r"^</?text>|</?text>$", "", s).strip()
    s = re.sub(r"^(translation|çeviri)\s*:\s*", "", s, flags=re.I)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'“”«»":
        s = s[1:-1].strip()
    return s
