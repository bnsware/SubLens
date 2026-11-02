"""Scan pipeline: capture -> OCR -> settle -> translate -> show.

Reading and translating run on separate threads so a slow engine never stops
the screen from being read (which is how v1 skipped lines). A line is sent for
translation once it has *settled* - two reads in a row agree - so fade-ins and
typewriter text are not translated half-finished.
"""
from __future__ import annotations

import difflib
import re
import threading
import time
from collections import OrderedDict, deque
from typing import Callable

from .capture import GRABBER, frame_signature, frame_changed
from .engines import Request
from .i18n import t
from .ocr import Reader, OcrResult
from .textproc import (similarity, normalize, parse_glossary, protect_terms,
                       restore_terms, glossary_terms_in, script_mismatch, garble,
                       fix_speakers, speakers_in)

SAME_TEXT = 0.88      # similarity at which two OCR reads count as the same subtitle
MAX_PENDING = 3       # translation backlog before the oldest pending line is dropped
CONTEXT_MAX_AGE = 90.0  # s - older lines are another scene and no longer sent as context
GARBLED = 0.15          # garble() above this looks like a half-faded / misread subtitle
GARBLED_PATIENCE = 1.2  # s to wait for such text to turn legible before sending it anyway
CORRECTION_SIM = 0.45   # a cleaner read this similar to the last line replaces it...
CORRECTION_WINDOW = 3.0  # ...if it comes within this many seconds
REREAD_SIM = 0.72       # this similar, not longer and not cleaner: the same subtitle misread again
FADE_OUT_KEEP = 0.85    # a "correction" shorter than this share of the line is it fading out
ROLL_FLUSH_AFTER = 1.5  # s without new words before an unfinished scrolling sentence is sent
ROLL_MAX_WORDS = 30     # ...or once it gets this long
_SENT_END = re.compile(r"[.!?…。！？]['\"”’)\]]*$")


class LRU:
    def __init__(self, cap=300):
        self.cap, self.d = cap, OrderedDict()

    def get(self, k):
        if k in self.d:
            self.d.move_to_end(k)
            return self.d[k]
        return None

    def put(self, k, v):
        self.d[k] = v
        self.d.move_to_end(k)
        while len(self.d) > self.cap:
            self.d.popitem(last=False)


class Events:
    """Callbacks the UI plugs in (called from worker threads)."""
    log: Callable[[str, str], None] = staticmethod(lambda msg, tag: None)
    ocr: Callable[[OcrResult], None] = staticmethod(lambda r: None)
    translated: Callable[[str, str], None] = staticmethod(lambda src, tr: None)
    cleared: Callable[[], None] = staticmethod(lambda: None)
    busy: Callable[[bool], None] = staticmethod(lambda b: None)


class Translator:
    """Ordered translation worker with cache, glossary and rolling context."""

    def __init__(self, cfg: dict, engines: dict, events: Events):
        self.cfg, self.engines, self.ev = cfg, engines, events
        self.cache = LRU()
        # the conversation so far: (time, source, translation)
        self.history: deque[tuple[float, str, str]] = deque(maxlen=16)
        self._q: deque[list] = deque()     # [text, is_scroll_chunk]
        self._cv = threading.Condition()
        self._stop = False
        self._gen = 0                      # bumped on discard() so in-flight results are dropped
        self._misread: deque[str] = deque(maxlen=20)   # lines replaced by a cleaner read
        self._glossary_src = None
        self._glossary: list = []
        threading.Thread(target=self._run, daemon=True, name="translator").start()

    def stop(self):
        with self._cv:
            self._stop = True
            self._cv.notify_all()

    def clear_cache(self):
        self.cache = LRU()

    def discard(self):
        """Forget pending work and ignore the result of the one in flight (on Stop)."""
        with self._cv:
            self._q.clear()
            self._gen += 1

    def submit(self, text: str, chunk: bool = False, corrects: str | None = None):
        """Queue a line. `corrects`: an earlier misread of this same line, which is
        dropped from the queue, kept out of the context and, if its translation is
        still in flight, never shown."""
        with self._cv:
            if corrects:
                self._misread.append(corrects)
                keep = [h for h in self.history if h[1] != corrects]
                self.history.clear()
                self.history.extend(keep)
                self._q = deque(i for i in self._q if i[0] != corrects)
            last = self._q[-1] if self._q else None
            if last and chunk and last[1]:
                # scrolling captions: new words join the waiting chunk, nothing is lost
                last[0] = f"{last[0]} {text}"
            elif last and not chunk and not last[1] and \
                    normalize(text).startswith(normalize(last[0])):
                # a growing line (typewriter effect) replaces its own pending prefix
                last[0] = text
            else:
                self._q.append([text, chunk])
            while len(self._q) > MAX_PENDING:
                dropped = self._q.popleft()[0]
                self.ev.log(t("Engine too slow, skipped: {}", dropped[:40]), "warn")
            self._cv.notify()

    def _glossary_list(self):
        g = self.cfg.get("glossary", "")
        if g != self._glossary_src:
            self._glossary_src, self._glossary = g, parse_glossary(g)
        return self._glossary

    def context(self, now: float | None = None) -> list[tuple[str, str]]:
        """Recent (source, translation) pairs - a long silence means a new scene."""
        now = time.monotonic() if now is None else now
        n = int(self.cfg.get("context_lines", 6))
        recent = [(s, o) for ts, s, o in self.history if now - ts <= CONTEXT_MAX_AGE]
        return recent[-n:] if n > 0 else []

    def remember(self, text: str, out: str, now: float | None = None):
        if self.history and self.history[-1][1] == text:
            return
        self.history.append((time.monotonic() if now is None else now, text, out))

    def translate_now(self, text: str) -> str:
        cfg = self.cfg
        key = cfg["engine"]
        eng = self.engines[key]
        eng.configure(cfg["engines"].get(key, {}))
        src, tgt = cfg["src_lang"], cfg["tgt_lang"]
        history = self.context()
        ck = f"{key}|{src}|{tgt}|{normalize(text)}"
        if (eng.is_llm or key == "deepl") and history:
            # a short reply means something different after a different line
            ck += "|" + normalize(history[-1][0])
        hit = self.cache.get(ck)
        if hit is not None:
            return hit
        glossary = self._glossary_list()
        if eng.is_llm:
            req = Request(text, src, tgt, cfg.get("ctx", ""), history,
                          glossary_terms_in(text, glossary))
            out = eng.translate(req)
        else:
            protected, ph = protect_terms(text, glossary)
            out = restore_terms(eng.translate(Request(protected, src, tgt, history=history)), ph)
        self.cache.put(ck, out)
        return out

    def _run(self):
        while True:
            with self._cv:
                while not self._q and not self._stop:
                    self._cv.wait()
                if self._stop:
                    return
                text = self._q.popleft()[0]
                gen = self._gen
            self.ev.busy(True)
            t0 = time.perf_counter()
            try:
                out = self.translate_now(text)
                if gen != self._gen or text in self._misread:
                    continue
                self.remember(text, out)
                ms = int((time.perf_counter() - t0) * 1000)
                self.ev.log(f"> {out}   ({ms} ms)", "tr")
                self.ev.translated(text, out)
            except Exception as e:
                self.ev.log(t("Translation error: {}", e), "err")
            finally:
                self.ev.busy(False)


class Settler:
    """Decides when OCR text is final and new. Pure logic - unit tested."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.candidate = ""
        self.candidate_since = 0.0
        self.last_sent = ""
        self.last_sent_at = 0.0
        self.corrects: str | None = None   # set when the returned text fixes a misread
        self.empty_since: float | None = None

    def feed(self, text: str, now: float, wait_stable: bool) -> str | None:
        """Returns text to translate, or None.

        When the result is a cleaner read of the subtitle sent just before (a
        fade-in first read as "Vücyrocyerrılzdcı ikramları", then correctly),
        `corrects` names the line it replaces.
        """
        self.corrects = None
        if not text:
            if self.empty_since is None:
                self.empty_since = now
            self.candidate = ""
            return None
        self.empty_since = None
        if not self.candidate or similarity(text, self.candidate) < SAME_TEXT:
            self.candidate, self.candidate_since = text, now
            if wait_stable:
                return None
        self.candidate = text
        # a half-faded subtitle reads as noise: give it time to become legible
        if (wait_stable and garble(text) > GARBLED and
                now - self.candidate_since < GARBLED_PATIENCE):
            return None
        if self.last_sent:
            sim = similarity(text, self.last_sent)
            if sim >= SAME_TEXT:
                return None
            n_new, n_old = len(normalize(text)), len(normalize(self.last_sent))
            cleaner = garble(text) < garble(self.last_sent)
            # "bem. Por isso." re-read as "bern Por isscL", or losing words as it fades out
            if (sim >= REREAD_SIM and n_new <= n_old * 1.1
                    and (not cleaner or n_new < n_old * FADE_OUT_KEEP)):
                return None
            if (cleaner and sim >= CORRECTION_SIM and n_new >= n_old * FADE_OUT_KEEP
                    and now - self.last_sent_at <= CORRECTION_WINDOW):
                self.corrects = self.last_sent
        self.last_sent, self.last_sent_at = text, now
        return text

    def gone_for(self, now: float) -> float:
        return 0.0 if self.empty_since is None else now - self.empty_since


def _fold(word: str) -> str:
    w = word.lower().replace("ı", "i").replace("i̇", "i")
    return re.sub(r"[\W_]+", "", w)


class Roller:
    """Turns settled screens into translation units. Pure logic - unit tested.

    Game subtitles replace each other, so each new screen is sent whole. Live
    captions (YouTube, streams, some games) scroll instead: every screen repeats
    the tail of the previous one. Those are followed as one word stream, only
    the new words are kept, and they go out a sentence at a time - otherwise the
    engine re-translates the same line two or three times and falls behind.
    feed()/tick()/flush() return [(text, is_scroll_chunk), ...].
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.words: list[str] = []
        self.sent = 0           # words[:sent] have been handed to the translator
        self.screen = 0         # index in words where the current screen starts
        self.rolling = False
        self.last_add = 0.0

    def _align(self, new: list[str]):
        """(screen_start, first_new_index, partial_fix) or None if `new` is unrelated."""
        base = max(0, len(self.words) - 60)
        old = [_fold(w) for w in self.words[base:]]
        cur = [_fold(w) for w in new]
        blocks = [b for b in difflib.SequenceMatcher(None, old, cur, autojunk=False)
                  .get_matching_blocks() if b.size]
        if sum(b.size for b in blocks) < min(2, len(cur)):
            return None
        tail = [b for b in blocks if b.a + b.size >= len(old) - 1]
        if not tail:
            return None
        a, b, size = tail[-1]
        # the last old word didn't match: it was half-typed or misread at the edge
        stale_last = a + size == len(old) - 1 and b + size < len(cur)
        return base + blocks[0].a - blocks[0].b, b + size, stale_last

    def feed(self, text: str, now: float) -> list[tuple[str, bool]]:
        new = text.split()
        if not new:
            return []
        al = self._align(new) if self.words else None
        if al is None:
            out = self.flush()
            self.words, self.sent, self.screen = new, len(new), 0
            self.rolling, self.last_add = False, now
            return out + [(text, False)]
        screen, nxt, stale_last = al
        if screen > self.screen:
            self.rolling = True     # the top of the previous screen scrolled away
        self.screen = max(self.screen, screen)
        changed = False
        if stale_last and len(self.words) - 1 >= self.sent:
            self.words.pop()        # "çı" -> "çıkmıyordu": the new read replaces it
            changed = True
        if nxt < len(new):
            self.words.extend(new[nxt:])
            changed = True
        if changed:
            self.last_add = now
        if not self.rolling:
            # still one subtitle growing in place: send it whole, as before
            if changed:
                self.sent = len(self.words)
                return [(text, False)]
            return []
        out = self._emit()
        self._trim()
        return out

    def _emit(self) -> list[tuple[str, bool]]:
        pend = self.words[self.sent:]
        end = max((i for i, w in enumerate(pend) if _SENT_END.search(w)), default=-1)
        if end < 0 and len(pend) >= ROLL_MAX_WORDS:
            end = len(pend) - 1
        if end < 0:
            return []
        self.sent += end + 1
        return [(" ".join(pend[:end + 1]), True)]

    def tick(self, now: float) -> list[tuple[str, bool]]:
        if self.rolling and self.sent < len(self.words) and now - self.last_add >= ROLL_FLUSH_AFTER:
            return self.flush()
        return []

    def flush(self) -> list[tuple[str, bool]]:
        if self.sent >= len(self.words):
            return []
        chunk = " ".join(self.words[self.sent:])
        self.sent = len(self.words)
        return [(chunk, True)]

    def _trim(self):
        drop = min(self.sent, self.screen) - 60
        if drop > 0:
            del self.words[:drop]
            self.sent -= drop
            self.screen -= drop


class Scanner:
    def __init__(self, cfg: dict, engines: dict, events: Events):
        self.cfg, self.ev = cfg, events
        self.reader = Reader()
        self.translator = Translator(cfg, engines, events)
        self.settler = Settler()
        self.roller = Roller()
        self._lang_warned = False
        self._speakers: dict[str, int] = {}
        self.running = False
        self.paused = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._cleared = True
        self._boxes: OrderedDict[str, tuple] = OrderedDict()

    def _remember_box(self, res: OcrResult, text: str):
        b = res.box()
        if b and text:
            self._boxes[text] = b
            while len(self._boxes) > 20:
                self._boxes.popitem(last=False)

    def text_region(self, text: str):
        """Screen rectangle (physical px) the subtitle text occupied, else the whole area."""
        r = self.cfg.get("region")
        b = self._boxes.get(text)
        if not r or not b:
            return r
        return (r[0] + b[0], r[1] + b[1], r[0] + b[2], r[1] + b[3])

    # -- one read ---------------------------------------------------------------
    def read_once(self) -> OcrResult:
        cfg = self.cfg
        if not cfg.get("region"):
            raise RuntimeError(t("Select the subtitle area first"))
        return self._read(GRABBER.grab(cfg["region"]))

    def _read(self, img) -> OcrResult:
        cfg = self.cfg
        return self.reader.read(img, cfg["src_lang"], cfg.get("text_style", "auto"),
                                int(cfg.get("ocr_scale", 0)))

    def translate_once(self):
        def run():
            try:
                res = self.read_once()
                self.ev.ocr(res)
                if not res.text:
                    self.ev.log(t("No text found in the area."), "warn")
                    return
                self.ev.log(f"OCR -> {res.text[:80]}", "dim")
                text = self._fix_speakers(res.text)
                self.settler.last_sent = text
                self._remember_box(res, text)
                self.translator.submit(text)
            except Exception as e:
                self.ev.log(str(e), "err")
        threading.Thread(target=run, daemon=True).start()

    # -- loop -------------------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        self.paused = False
        self._stop.clear()
        self.settler.reset()
        self.roller.reset()
        self._lang_warned = False
        self._thread = threading.Thread(target=self._loop, daemon=True, name="scanner")
        self._thread.start()

    def stop(self):
        self.running = False
        self._stop.set()
        self.translator.discard()

    def _fix_speakers(self, text: str) -> str:
        # a name counts once it has been seen with a proper colon twice
        return fix_speakers(text, [n for n, c in self._speakers.items() if c >= 2])

    def _send(self, items, now, corrects: str | None = None):
        for text, chunk in items:
            self._cleared = False
            for name in speakers_in(text):
                self._speakers[name] = self._speakers.get(name, 0) + 1
            self.ev.log(f"{'Fixed' if corrects else 'New'} -> {text[:70]}", "dim")
            self.translator.submit(text, chunk, corrects)
            if not self._lang_warned:
                hint = script_mismatch(text, self.cfg["src_lang"])
                if hint:
                    self._lang_warned = True
                    self.ev.log(hint, "warn")

    def shutdown(self):
        self.stop()
        self.translator.stop()

    def _loop(self):
        prev_sig = None
        last_text = ""
        last_preview = 0.0
        errors = 0
        while self.running:
            t0 = time.perf_counter()
            if self.paused:
                if self._stop.wait(0.4):
                    break
                continue
            try:
                img = GRABBER.grab(self.cfg["region"])
                sig = frame_signature(img)
                if frame_changed(prev_sig, sig):
                    res = self._read(img)
                    last_text = self._fix_speakers(res.text)
                    self._remember_box(res, last_text)
                    if time.monotonic() - last_preview > 1.0:
                        last_preview = time.monotonic()
                        self.ev.ocr(res)
                prev_sig = sig
                errors = 0
                now = time.monotonic()
                # an unchanged frame repeats the last read, which also settles it
                out = self.settler.feed(last_text, now, bool(self.cfg.get("wait_stable", True)))
                if out and self.settler.corrects and not self.roller.rolling:
                    # a cleaner read of the line just sent: it replaces that line
                    self.roller.reset()
                    self._send(self.roller.feed(out, now), now, self.settler.corrects)
                elif out:
                    self._send(self.roller.feed(out, now), now)
                self._send(self.roller.tick(now), now)
                hide_after = float(self.cfg.get("overlay_hide_after", 2.0))
                if (hide_after > 0 and not self._cleared
                        and self.settler.gone_for(now) >= hide_after):
                    self._send(self.roller.flush(), now)
                    self.roller.reset()
                    self._cleared = True
                    self.settler.last_sent = ""
                    self.ev.cleared()
            except Exception as e:
                errors += 1
                if errors <= 3:
                    self.ev.log(t("Read error: {}", e), "err")
                if errors >= 3 and self._stop.wait(2.0):
                    break
            interval = max(0.08, float(self.cfg.get("interval", 0.25)))
            if self._stop.wait(max(0.02, interval - (time.perf_counter() - t0))):
                break
