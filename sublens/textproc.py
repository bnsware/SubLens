"""Text cleanup between OCR and translation.

OCR backends return lines of positioned words. Everything here is pure Python
so it can be unit tested without a screen:
  - icon / button-prompt / symbol removal (position + size aware)
  - joining wrapped subtitle lines into sentences, keeping speaker turns apart
  - normalisation + similarity for change detection
  - glossary (term protection)
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass


@dataclass
class Word:
    text: str
    x: float
    y: float
    w: float
    h: float

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def cy(self) -> float:
        return self.y + self.h / 2


Line = list[Word]

_SYMBOL_CATS = ("So", "Sk", "Co", "Cn", "Cs")
# Characters that OCR typically produces from button glyphs, frames and dividers
_JUNK_CHARS = set("|¦©®™€¥§¶•○●◯□■◆◇▲△▼▽►◄★☆♦♣♠♥→←↑↓⟵⟶«»~_=+^*<>{}[]\\/@#$%&")
_EDGE_PUNCT = "|¦[](){}<>«»~_=+^*•·'\"`"
# Short tokens that are real words and must never be treated as icons
_SHORT_WORDS = {"i", "a", "o", "y", "e", "u", "ok", "no", "go", "oh", "ah", "uh", "hm",
                "me", "we", "he", "it", "is", "to", "do", "so", "up", "on", "in", "an",
                "at", "be", "by", "my", "of", "or", "us", "if", "ya", "yo", "hi"}


def strip_symbols(s: str) -> str:
    return "".join(c for c in s if not unicodedata.category(c).startswith(_SYMBOL_CATS))


def clean_token(tok: str) -> str:
    tok = strip_symbols(tok).strip()
    # Leading/trailing frame characters ("|Hello", "[E]") - keep inner text
    tok = tok.strip(_EDGE_PUNCT)
    return tok


def is_noise_token(tok: str) -> bool:
    if not tok:
        return True
    letters = sum(1 for c in tok if c.isalpha())
    digits = sum(1 for c in tok if c.isdigit())
    if letters == 0 and digits == 0:
        # pure punctuation is allowed only as sentence punctuation ("...", "-", "?!")
        return not all(c in ".,!?;:-–—…'\"" for c in tok)
    junk = sum(1 for c in tok if c in _JUNK_CHARS)
    if junk and junk >= max(1, len(tok) // 3):
        return True
    return False


def _is_short_glyph(tok: str) -> bool:
    """A 1-2 char token that looks like a button label (X, R1, LB, Ⓐ->A)."""
    t = tok.strip(".,!?:;")
    if not t or len(t) > 2:
        return False
    return t.lower() not in _SHORT_WORDS or (len(t) == 1 and t.isupper() and t not in ("I", "A", "O"))


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    if not s:
        return 0.0
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def dominant_height(lines: list[Line]) -> float:
    """Glyph height of the dialogue text: the tallest real-text line.

    Subtitles are the largest text in a subtitle region; hints and labels are
    smaller, so the tallest line with actual words is the reference.
    """
    best = 0.0
    for line in lines:
        if sum(c.isalpha() for w in line for c in w.text) >= 4:
            best = max(best, _median([w.h for w in line if any(c.isalpha() for c in w.text)]))
    return best or _median([w.h for line in lines for w in line])


def clean_lines(lines: list[Line]) -> list[Line]:
    """Remove icons, button prompts, stray symbols and off-size UI text."""
    # 1) token level
    tmp: list[Line] = []
    for line in lines:
        out = []
        for w in line:
            t = clean_token(w.text)
            if is_noise_token(t):
                continue
            out.append(Word(t, w.x, w.y, w.w, w.h))
        if out:
            tmp.append(sorted(out, key=lambda w: w.x))
    if not tmp:
        return []

    H = dominant_height(tmp) or 1.0

    # 2) size filter: glyphs much smaller / larger than the dialog text
    sized: list[Line] = []
    for line in tmp:
        kept = [w for w in line if 0.5 * H <= w.h <= 2.1 * H]
        if kept:
            sized.append(kept)

    # 3) isolated short tokens at line edges are almost always button icons
    edge_gap = 0.9 * H
    result: list[Line] = []
    for line in sized:
        changed = True
        while changed and line:
            changed = False
            if len(line) == 1:
                break
            first, second = line[0], line[1]
            if _is_short_glyph(first.text) and second.x - first.right > edge_gap:
                line = line[1:]
                changed = True
                continue
            last, prev = line[-1], line[-2]
            if _is_short_glyph(last.text) and last.x - prev.right > edge_gap:
                line = line[:-1]
                changed = True
        # A line that is a single short glyph on its own is an icon too
        if len(line) == 1 and _is_short_glyph(line[0].text):
            continue
        alpha = sum(c.isalpha() for w in line for c in w.text)
        if alpha < 2:
            continue
        # Lines in a noticeably smaller font are UI hints ("Hold E to skip")
        if _median([w.h for w in line]) < 0.62 * H and len(sized) > 1:
            continue
        result.append(line)
    return result


def group_into_lines(words: list[Word]) -> list[Line]:
    """Group loose words into visual lines (for backends without line info)."""
    if not words:
        return []
    H = _median([w.h for w in words]) or 1
    tol = max(3, H * 0.5)
    lines: list[Line] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x)):
        for line in lines:
            cy = sum(x.cy for x in line) / len(line)
            if abs(w.cy - cy) <= tol:
                line.append(w)
                break
        else:
            lines.append([w])
    for line in lines:
        line.sort(key=lambda w: w.x)
    lines.sort(key=lambda l: min(w.y for w in l))
    return lines


_SPEAKER_RE = re.compile(r"^[A-Z0-9][\w .'\-]{0,24}:\s")


def lines_to_text(lines: list[Line]) -> str:
    """Join wrapped lines into one sentence; start a new paragraph on a speaker tag."""
    paragraphs: list[str] = []
    for line in lines:
        s = " ".join(w.text for w in line)
        s = re.sub(r"\s+", " ", s).strip()
        s = re.sub(r"\s+([,.!?;:…])", r"\1", s)
        if not s:
            continue
        if paragraphs and not _SPEAKER_RE.match(s):
            prev = paragraphs[-1]
            if prev.endswith("-") and not prev.endswith(" -"):
                paragraphs[-1] = prev[:-1] + s
            else:
                paragraphs[-1] = prev + " " + s
        else:
            paragraphs.append(s)
    return "\n".join(paragraphs)


_TAG = re.compile(r"([\W_]*)([^\W\d_][\w'’\- ]{0,24}?)\s*([:.•·]+)\s+(\S.*)", re.S)


def speaker_name(tag: str) -> str | None:
    """`tag` as a speaker label ("Tia May", "MJ", "ARTHUR"), or None if it reads like words."""
    words = tag.split()
    if not 1 <= len(words) <= 2 or len(tag) < 2:
        return None
    if all(w[0].isupper() for w in words):
        return tag
    return None


def resolve_speaker(name: str, known, min_cut: int = 3) -> str | None:
    """Map a read name to a known speaker; the region's edge often cuts its first letters
    ("eter" -> "Peter", "arry" -> "Harry")."""
    low = name.lower()
    for k in known:
        kl = k.lower()
        if low == kl:
            return k
        if len(low) >= min_cut and len(low) >= len(kl) - 2 and kl.endswith(low):
            return k
        if low.endswith(" " + kl):          # "TER PARKER Peter" -> "Peter"
            return k
    return None


def fix_speakers(text: str, known) -> str:
    """Normalise speaker labels at the start of each paragraph to "Name: ...".

    OCR turns "Peter:" into "Peter.", ".Harry•.", "eter:" or drops the colon
    altogether; translators then treat the name as part of the sentence
    ("Peter especial." -> "Özel Peter."). Only names already seen with a
    proper colon (`known`) are repaired, so ordinary sentences are left alone.
    """
    out = []
    for p in text.split("\n"):
        m = _TAG.fullmatch(p)
        if m:
            name, sep, body = m.group(2).strip(), m.group(3), m.group(4)
            k = resolve_speaker(name, known)
            if k or (":" in sep and speaker_name(name)):
                out.append(f"{k or name}: {body}")
                continue
        # no separator left at all: "eter Espera," / "Tia May Vá, anda"
        words = p.lstrip(".,;:•·-–—*'\" ").split(" ")
        for n in (2, 1):
            if len(words) > n and words[n][:1].isalnum():
                k = resolve_speaker(" ".join(words[:n]), known, min_cut=4)
                if k:
                    out.append(f"{k}: {' '.join(words[n:])}")
                    break
        else:
            out.append(p)
    return "\n".join(out)


def speakers_in(text: str) -> list[str]:
    """Names introduced with a real colon ("Tia May: ..."), to learn from."""
    names = []
    for p in text.split("\n"):
        m = _TAG.fullmatch(p)
        if m and ":" in m.group(3) and not m.group(1).strip():
            n = speaker_name(m.group(2).strip())
            if n:
                names.append(n)
    return names


def normalize(text: str) -> str:
    return re.sub(r"[\W_]+", "", (text or "").lower())


def similarity(a: str, b: str) -> float:
    na, nb = normalize(a), normalize(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()


_CJK = re.compile(r"[぀-ヿ㐀-鿿가-힯]")
_CYR = re.compile(r"[Ѐ-ӿ]")
_TR_ONLY = re.compile(r"[ğşıİĞŞ]")


def script_mismatch(text: str, src_lang: str) -> str | None:
    """A hint when the text clearly isn't in the chosen source language."""
    letters = sum(c.isalpha() for c in text)
    if letters < 12 or src_lang == "Auto-Detect":
        return None
    cjk, cyr = len(_CJK.findall(text)), len(_CYR.findall(text))
    latin = letters - cjk - cyr
    if src_lang in ("Chinese", "Japanese", "Korean"):
        wrong = cjk < letters * 0.2
    elif src_lang == "Russian":
        wrong = cyr < letters * 0.3
    else:
        wrong = latin < letters * 0.5
    from .i18n import t
    if not wrong and src_lang != "Turkish" and len(_TR_ONLY.findall(text)) >= 2:
        return t("The text looks Turkish but the source language is {} - change it, "
                 "or reading and translation suffer.", t(src_lang))
    if wrong:
        return t("The text doesn't look like {} - check the source language, "
                 "or reading and translation suffer.", t(src_lang))
    return None


_VOWELS = set("aeiouyàáâäãåæèéêëìíîïòóôöõøœùúûüıi̇")
_CONS_RUN = re.compile(r"[^\W\d_aeiouyàáâäãåæèéêëìíîïòóôöõøœùúûüı]{4,}")
_LATIN = re.compile(r"^[a-zà-öø-ÿçğışñßłńśźżčřšžđœæ]+$")
_DIGRAPHS = ("th", "ch", "sh", "ph", "gh", "ck", "sch")   # "months", "strength", "Schmidt"


def _noisy_run(run: str) -> bool:
    return len(run) >= 5 or not any(d in run for d in _DIGRAPHS)


def garble(text: str) -> float:
    """Share of Latin-script words that look like OCR noise (0 = clean, 1 = all noise).

    A half-faded subtitle reads as "Vücyrocyerrılzdcı ikramları" or "değil rnl?":
    no vowel at all, four consonants in a row, or case flipping inside a word.
    Other scripts aren't judged (returns 0).
    """
    words = [w.strip(".,!?;:\"'()-…“”’‘") for w in text.split()]
    latin = [w for w in words if len(w) >= 3 and _LATIN.match(w.lower())]
    if not latin:
        return 0.0
    bad = 0
    for w in latin:
        if w.isupper():                 # acronyms, shouted lines
            continue
        lw = w.lower()
        if (not any(c in _VOWELS for c in lw)
                or any(_noisy_run(m.group()) for m in _CONS_RUN.finditer(lw))
                or any(c.isupper() for c in w[1:])):
            bad += 1
    return bad / len(latin)


def text_score(text: str) -> float:
    """How much this looks like real language (used to pick the best OCR setting)."""
    score = 0.0
    for tok in text.split():
        t = tok.strip(".,!?;:\"'()-…")
        if not t:
            continue
        letters = sum(c.isalpha() for c in t)
        if letters == len(t) and len(t) >= 2:
            score += len(t)
            # mixed case in the middle of a word ("hElLo") is typical OCR garbage
            if any(c.isupper() for c in t[1:]) and not t.isupper():
                score -= len(t) * 0.7
        elif letters >= len(t) * 0.6:
            score += len(t) * 0.3
        else:
            score -= 2
    return score


# -----------------------------------------------------------------------------
#  Glossary
# -----------------------------------------------------------------------------

def parse_glossary(text: str) -> list[tuple[str, str]]:
    """Each line is 'source=target' or just 'source' (keep as-is). '#' starts a comment."""
    out = []
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if "=" in line:
            src, tgt = (p.strip() for p in line.split("=", 1))
        else:
            src = tgt = line
        if src:
            out.append((src, tgt or src))
    out.sort(key=lambda kv: -len(kv[0]))
    return out


def protect_terms(text: str, glossary: list[tuple[str, str]]) -> tuple[str, dict[str, str]]:
    """Replace glossary terms with numbered tokens that MT engines leave alone."""
    placeholders: dict[str, str] = {}
    out = text
    for i, (src, tgt) in enumerate(glossary):
        pattern = re.compile(rf"(?i)(?<!\w){re.escape(src)}(?!\w)")
        if pattern.search(out):
            token = f"ZXQ{i}Q"
            out = pattern.sub(token, out)
            placeholders[token] = tgt
    return out, placeholders


def restore_terms(text: str, placeholders: dict[str, str]) -> str:
    for token, tgt in placeholders.items():
        # engines sometimes change case or add spaces inside the token
        idx = token[3:-1]
        text = re.sub(rf"(?i)Z\s*X\s*Q\s*{idx}\s*Q", lambda _m, t=tgt: t, text)
    return text


def glossary_terms_in(text: str, glossary: list[tuple[str, str]]) -> list[tuple[str, str]]:
    low = text.lower()
    return [(s, t) for s, t in glossary if s.lower() in low]
