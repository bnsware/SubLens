import copy
import threading
import time
import unittest

from sublens import config
from sublens.engines.base import Request, build_llm_prompt, clean_llm_output
from sublens.pipeline import Settler, Translator, Events, Roller
from sublens.textproc import script_mismatch, garble, fix_speakers, speakers_in
from sublens.textproc import (Word, clean_lines, lines_to_text, parse_glossary,
                              protect_terms, restore_terms, similarity, text_score,
                              group_into_lines)


def line(*specs, y=100, h=24):
    """specs: (text, x, width)"""
    return [Word(t, x, y, w, h) for t, x, w in specs]


class TestCleanLines(unittest.TestCase):
    def test_button_icon_at_line_start_removed(self):
        l = line(("X", 10, 22), ("Skip", 70, 50), ("dialogue", 128, 90))
        self.assertEqual(lines_to_text(clean_lines([l])), "Skip dialogue")

    def test_button_icon_at_line_end_removed(self):
        l = line(("Hold", 10, 50), ("to", 66, 22), ("skip", 94, 45), ("R1", 190, 28))
        self.assertEqual(lines_to_text(clean_lines([l])), "Hold to skip")

    def test_real_short_words_kept(self):
        l = line(("I", 10, 8), ("know", 24, 50), ("a", 80, 12), ("guy.", 98, 44))
        self.assertEqual(lines_to_text(clean_lines([l])), "I know a guy.")

    def test_symbols_and_frames_removed(self):
        l = line(("©", 10, 20), ("|Where", 40, 70), ("are", 116, 36), ("you?", 158, 50), ("•", 220, 10))
        self.assertEqual(lines_to_text(clean_lines([l])), "Where are you?")

    def test_small_ui_hint_line_dropped(self):
        main = line(("We", 10, 30), ("have", 46, 50), ("to", 102, 20), ("move!", 128, 60))
        hint = line(("Press", 10, 30), ("to", 44, 12), ("continue", 60, 50), y=150, h=11)
        self.assertEqual(lines_to_text(clean_lines([main, hint])), "We have to move!")

    def test_lone_icon_line_dropped(self):
        main = line(("Come", 10, 50), ("on!", 66, 36))
        icon = line(("Y", 300, 22), y=140)
        self.assertEqual(lines_to_text(clean_lines([main, icon])), "Come on!")


class TestLineJoining(unittest.TestCase):
    def test_wrapped_lines_become_one_sentence(self):
        l1 = line(("I", 10, 8), ("told", 24, 44), ("you", 74, 36), ("we", 116, 28), ("should", 150, 66))
        l2 = line(("have", 10, 50), ("waited", 66, 66), ("here.", 138, 52), y=130)
        self.assertEqual(lines_to_text(clean_lines([l1, l2])),
                         "I told you we should have waited here.")

    def test_hyphenated_word_rejoined(self):
        l1 = line(("This", 10, 40), ("is", 56, 16), ("unbeliev-", 78, 90))
        l2 = line(("able!", 10, 50), y=130)
        self.assertEqual(lines_to_text(clean_lines([l1, l2])), "This is unbelievable!")

    def test_speaker_change_starts_new_paragraph(self):
        l1 = line(("MILES:", 10, 70), ("You", 86, 40), ("ready?", 132, 60))
        l2 = line(("PETER:", 10, 70), ("Always.", 86, 70), y=130)
        self.assertEqual(lines_to_text(clean_lines([l1, l2])), "MILES: You ready?\nPETER: Always.")

    def test_group_into_lines(self):
        ws = [Word("world", 70, 102, 50, 22), Word("Hello", 10, 100, 50, 24),
              Word("Next", 10, 140, 40, 24)]
        lines = group_into_lines(ws)
        self.assertEqual([[w.text for w in l] for l in lines], [["Hello", "world"], ["Next"]])


class TestSpeakers(unittest.TestCase):
    KNOWN = ["Peter", "Harry", "Tia May", "MJ"]

    def test_learns_only_real_tags(self):
        self.assertEqual(speakers_in("Tia May: Todos os anos"), ["Tia May"])
        self.assertEqual(speakers_in("MJ: Recebi uma dica.\nPeter: Disseram quem?"), ["MJ", "Peter"])
        self.assertEqual(speakers_in("Não, mas vou descobrir."), [])
        self.assertEqual(speakers_in("Recebi uma dica: amanhã"), [])

    def test_damaged_tags_repaired(self):
        cases = {
            "eter: Que saudades, amigo.": "Peter: Que saudades, amigo.",
            "arry: Isto é novo.": "Harry: Isto é novo.",
            ".Harry•. Whoa!": "Harry: Whoa!",
            "Peter. MJ?": "Peter: MJ?",
            "Tia May. fui-me abaixo.": "Tia May: fui-me abaixo.",
            "TER PARKER Peter: Não posso": "Peter: Não posso",
            "Peter especial.": "Peter: especial.",
            "eter Espera,": "Peter: Espera,",
            "Tia May Vá, anda": "Tia May: Vá, anda",
            ";Harry: Não ias": "Harry: Não ias",
        }
        for src, want in cases.items():
            self.assertEqual(fix_speakers(src, self.KNOWN), want, src)

    def test_ordinary_sentences_untouched(self):
        for s in ("Não, mas vou descobrir.", "Eu tinha ido logo ter contigo.",
                  "Bom dia. Como vai?", "ter algo assim", "Harry, isso é.-"):
            self.assertEqual(fix_speakers(s, self.KNOWN), s)
        self.assertEqual(fix_speakers("eter: oi", []), "eter: oi")


class TestScoring(unittest.TestCase):
    def test_similarity(self):
        self.assertGreater(similarity("We have to go now!", "We have to go now"), 0.95)
        self.assertLess(similarity("We have to go now!", "Where is the car?"), 0.6)

    def test_text_score_prefers_language(self):
        self.assertGreater(text_score("We have to get to the bridge"), text_score("W3 h@v3 tO g;t |o"))


class TestGlossary(unittest.TestCase):
    def test_roundtrip(self):
        g = parse_glossary("Dutch\nSaint Denis=Saint Denis  # city\n# comment\nArthur=Arthur")
        protected, ph = protect_terms("Dutch wants Arthur in Saint Denis.", g)
        self.assertNotIn("Dutch", protected)
        # simulate an engine that lowercases and spaces the tokens
        mangled = protected.replace("ZXQ", "zxq ").lower()
        self.assertEqual(restore_terms(mangled, ph).count("Arthur"), 1)
        self.assertIn("Saint Denis", restore_terms(mangled, ph))
        self.assertIn("Dutch", restore_terms(mangled, ph))


class TestSettler(unittest.TestCase):
    def test_waits_for_two_matching_reads(self):
        s = Settler()
        self.assertIsNone(s.feed("We have to", 0.0, True))
        self.assertIsNone(s.feed("We have to go now, Miles!", 0.25, True))
        self.assertEqual(s.feed("We have to go now, Miles!", 0.5, True), "We have to go now, Miles!")
        self.assertIsNone(s.feed("We have to go now, Miles!", 0.75, True))   # no repeat

    def test_ocr_jitter_is_not_retranslated(self):
        s = Settler()
        s.feed("Get to the bridge!", 0, False)
        self.assertIsNone(s.feed("Get to the bridqe!", 0.25, False))

    def test_new_line_after_old(self):
        s = Settler()
        s.feed("First line here.", 0, False)
        self.assertEqual(s.feed("Second, different line.", 0.25, False), "Second, different line.")

    def test_gone_timer(self):
        s = Settler()
        s.feed("Hello there friend", 0, False)
        s.feed("", 1.0, False)
        self.assertAlmostEqual(s.gone_for(3.0), 2.0)

    def test_fading_subtitle_waits_for_the_clean_read(self):
        # from the user's log: a fade-in read as noise, then correctly
        s, out = Settler(), []
        for i, text in enumerate(["Vücyrocyerrılzdcı ikramları"] * 3 + ["Müessesemizden ikramlar!"] * 2):
            r = s.feed(text, i * 0.25, True)
            if r:
                out.append(r)
        self.assertEqual(out, ["Müessesemizden ikramlar!"])

    def test_late_clean_read_replaces_the_misread(self):
        s, now, sent = Settler(), 0.0, []
        for _ in range(7):                      # noise that stays longer than the patience
            r = s.feed("Bu çcce son accen değil rnl?", now, True)
            sent += [r] if r else []
            now += 0.25
        self.assertEqual(sent, ["Bu çcce son accen değil rnl?"])
        self.assertIsNone(s.feed("Bu gece son akşam değil mi?", now, True))
        self.assertEqual(s.feed("Bu gece son akşam değil mi?", now + 0.25, True),
                         "Bu gece son akşam değil mi?")
        self.assertEqual(s.corrects, "Bu çcce son accen değil rnl?")
        # an unrelated next line is not a correction
        s.feed("Hevesli gösterme kendini.", now + 1, True)
        s.feed("Hevesli gösterme kendini.", now + 1.25, True)
        self.assertIsNone(s.corrects)

    def test_reread_of_the_same_line_is_not_sent_again(self):
        # from the user's log (Spider-Man 2): one subtitle, read three ways as it fades
        s, out = Settler(), []
        reads = ["não fazià nada bem. Por isso."] * 2 + ["não fazia nada bern Por isscL"] * 6 \
            + ["não fazia nada bem Por"] * 2
        for i, text in enumerate(reads):
            r = s.feed(text, i * 0.25, True)
            if r:
                out.append(r)
        self.assertEqual(out, ["não fazià nada bem. Por isso."])
        self.assertIsNone(s.corrects)
        # the next subtitle still goes through
        self.assertEqual([s.feed("fiz menos coisas.", t, True) for t in (3.0, 3.25)][-1],
                         "fiz menos coisas.")

    def test_garble(self):
        self.assertGreater(garble("Vücyrocyerrılzdcı ikramları"), 0.15)
        self.assertGreater(garble("Bu çcce son accen değil rnl?"), 0.15)
        for ok in ("Müessesemizden ikramlar!", "Three months of strength training.",
                   "I saw Schmidt at the NPC STUDIO", "Spider-Man swings through Manhattan"):
            self.assertEqual(garble(ok), 0.0, ok)


class SlowEngine:
    key = "fake"; name = "Fake"; is_llm = False

    def __init__(self):
        self.seen = []

    def configure(self, cfg):
        pass

    def translate(self, req):
        time.sleep(0.05)
        self.seen.append(req.text)
        return req.text.upper()


class TestTranslator(unittest.TestCase):
    def test_order_cache_and_glossary(self):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["engine"] = "fake"
        cfg["engines"]["fake"] = {}
        cfg["glossary"] = "Dutch"
        eng = SlowEngine()
        done = []
        ev = Events()
        ev.translated = lambda s, t: done.append(t)
        tr = Translator(cfg, {"fake": eng}, ev)
        for t in ("one line", "two line", "one line"):
            tr.submit(t)
            time.sleep(0.1)
        tr.submit("Dutch says hi")
        deadline = time.time() + 2
        while len(done) < 4 and time.time() < deadline:
            time.sleep(0.02)
        tr.stop()
        self.assertEqual(done[:3], ["ONE LINE", "TWO LINE", "ONE LINE"])
        self.assertEqual(eng.seen.count("one line"), 1)  # cached second time
        self.assertEqual(done[3], "Dutch SAYS HI")       # glossary term survived

    def test_typewriter_replaces_pending(self):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["engine"] = "fake"
        cfg["engines"]["fake"] = {}
        eng = SlowEngine()
        ev = Events()
        tr = Translator(cfg, {"fake": eng}, ev)
        gate = threading.Event()
        orig = eng.translate
        eng.translate = lambda req: (gate.wait(), orig(req))[1]
        tr.submit("blocker")
        time.sleep(0.05)
        tr.submit("Hello")
        tr.submit("Hello there")
        tr.submit("Hello there, partner")
        gate.set()
        time.sleep(0.4)
        tr.stop()
        self.assertEqual(eng.seen, ["blocker", "Hello there, partner"])


    def test_context_pairs_and_context_aware_cache(self):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["engine"] = "fake"
        cfg["engines"]["fake"] = {}
        seen = []

        class LlmEngine(SlowEngine):
            is_llm = True

            def translate(self, req):
                seen.append(list(req.history))
                return f"{req.text}#{len(req.history)}"

        tr = Translator(cfg, {"fake": LlmEngine()}, Events())
        tr.remember("Bunu denemelisin.", "You should try this.", now=time.monotonic())
        self.assertEqual(tr.translate_now("Neyi?"), "Neyi?#1")
        self.assertEqual(seen[-1], [("Bunu denemelisin.", "You should try this.")])
        # same words after another line: not served from the cache
        tr.remember("Şunu al.", "Take this.", now=time.monotonic())
        tr.translate_now("Neyi?")
        self.assertEqual(len(seen), 2)
        # lines from long ago are another scene
        tr.history.clear()
        tr.remember("Eski sahne.", "Old scene.", now=time.monotonic() - 600)
        self.assertEqual(tr.context(), [])
        tr.stop()

    def test_no_translation_shows_text_as_read(self):
        from sublens.engines import create_all
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["engine"] = "none"
        cfg["glossary"] = "Dutch"
        tr = Translator(cfg, create_all(), Events())
        self.assertEqual(tr.translate_now("Dutch says: get the horses."),
                         "Dutch says: get the horses.")

    def test_correction_drops_the_misread(self):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["engine"] = "fake"
        cfg["engines"]["fake"] = {}
        eng = SlowEngine()
        done = []
        ev = Events()
        ev.translated = lambda s, t: done.append(s)
        tr = Translator(cfg, {"fake": eng}, ev)
        gate = threading.Event()
        orig = eng.translate
        eng.translate = lambda req: (gate.wait(), orig(req))[1]
        tr.submit("blocker")
        time.sleep(0.05)
        tr.submit("Vücyrocyerrılzdcı ikramları")            # still waiting in the queue
        tr.submit("Müessesemizden ikramlar!", corrects="Vücyrocyerrılzdcı ikramları")
        gate.set()
        time.sleep(0.4)
        tr.stop()
        self.assertEqual(eng.seen, ["blocker", "Müessesemizden ikramlar!"])
        self.assertEqual([s for _, s, _ in tr.history], ["blocker", "Müessesemizden ikramlar!"])

    def test_scroll_chunks_merge_instead_of_dropping(self):
        cfg = copy.deepcopy(config.DEFAULTS)
        cfg["engine"] = "fake"
        cfg["engines"]["fake"] = {}
        eng = SlowEngine()
        ev = Events()
        logs = []
        ev.log = lambda m, t: logs.append(m)
        tr = Translator(cfg, {"fake": eng}, ev)
        gate = threading.Event()
        orig = eng.translate
        eng.translate = lambda req: (gate.wait(), orig(req))[1]
        tr.submit("blocker")
        time.sleep(0.05)
        for i in range(6):
            tr.submit(f"part{i}.", chunk=True)
        gate.set()
        time.sleep(0.4)
        tr.stop()
        self.assertEqual(eng.seen, ["blocker", "part0. part1. part2. part3. part4. part5."])
        self.assertFalse(any("skipped" in m for m in logs))


# screens of a scrolling YouTube caption, as read in the user's log
SCROLL = [
    "abi? Hani millet maliyet kisma derdinde hani yeter paranmz",
    "abi? Hani millet maliyet kisma derdinde hani yeter paranmz yok artlk q",
    "hani yeter paranmz yok artlk qallan mallan Gikartahm",
    "mallan Gikartahm diye millet etrafa koşuyor.",
    "etrafa koşuyor. Dedik ki ya hadi",
    "Dedik ki ya hadi ikinci sezonu da çekelim. Bu sefer dedik",
    "ikinci sezonu da çekelim. Bu sefer dedik konuklar dan",
]


class TestRoller(unittest.TestCase):
    def run_screens(self, screens, dt=0.8):
        r, out, now = Roller(), [], 0.0
        for s in screens:
            now += dt
            out += r.feed(s, now)
            out += r.tick(now)
        return r, out, now

    def test_game_subtitles_go_whole(self):
        _, out, _ = self.run_screens(["Arthur, get the horses.", "We ride at dawn, boys."])
        self.assertEqual(out, [("Arthur, get the horses.", False), ("We ride at dawn, boys.", False)])

    def test_typewriter_grows_in_place(self):
        _, out, _ = self.run_screens(["Hello the", "Hello there my friend."])
        self.assertEqual(out[-1], ("Hello there my friend.", False))

    def test_scrolling_captions_become_sentences(self):
        r, out, now = self.run_screens(SCROLL)
        # screens 1-2 grow in place and go whole; from the first scroll only new words go
        self.assertEqual([c for _, c in out[:2]], [False, False])
        chunks = [t for t, c in out if c]
        self.assertEqual(chunks, ["qallan mallan Gikartahm diye millet etrafa koşuyor.",
                                  "Dedik ki ya hadi ikinci sezonu da çekelim."])
        # the unfinished tail goes out after a pause, with the partial word completed
        self.assertEqual(r.tick(now + 0.5), [])
        self.assertEqual(r.feed("Bu sefer dedik konuklar da olsun", now + 1), [])
        self.assertEqual(r.tick(now + 3), [("Bu sefer dedik konuklar da olsun", True)])

    def test_unrelated_screen_flushes_and_restarts(self):
        r, out, now = self.run_screens(SCROLL)
        out = r.feed("Completely different subtitle here", now + 0.5)
        self.assertEqual(out, [("Bu sefer dedik konuklar dan", True),
                               ("Completely different subtitle here", False)])

    def test_language_hint(self):
        self.assertIsNotNone(script_mismatch("tercih ediyoruz. Çünkü sohbetler daha temiz", "Chinese"))
        self.assertIsNotNone(script_mismatch("Hani yeter paramız yok artık çıkartalım şimdi", "English"))
        self.assertIsNone(script_mismatch("Get the horses ready, we ride at dawn", "English"))


class TestPrompt(unittest.TestCase):
    def test_prompt_replays_conversation(self):
        sys_p, turns = build_llm_prompt(Request(
            "Neyi?", "Turkish", "English", "RDR2, 1899",
            [("Bunu denemelisin.", "You should try this.")], [("Dutch", "Dutch")]))
        self.assertIn("English", sys_p)
        self.assertIn("RDR2, 1899", sys_p)
        self.assertIn("Dutch -> Dutch", sys_p)
        self.assertIn("Try what?", sys_p)
        self.assertEqual(turns, [("user", "<text>\nBunu denemelisin.\n</text>"),
                                 ("assistant", "You should try this."),
                                 ("user", "<text>\nNeyi?\n</text>")])

    def test_clean_output(self):
        self.assertEqual(clean_llm_output("<think>hmm</think>\n\"Hadi!\""), "Hadi!")
        self.assertEqual(clean_llm_output("Translation: Hadi"), "Hadi")


class TestI18n(unittest.TestCase):
    def test_every_ui_string_has_turkish(self):
        import ast
        from pathlib import Path
        from sublens import i18n
        from sublens.engines import create_all
        root = Path(__file__).resolve().parents[1] / "sublens"
        keys = set(config.SRC_LANGS)
        keys |= {e.note for e in create_all().values()}
        for py in root.rglob("*.py"):
            for node in ast.walk(ast.parse(py.read_text(encoding="utf-8"))):
                if (isinstance(node, ast.Call) and getattr(node.func, "id", "") == "t"
                        and node.args and isinstance(node.args[0], ast.Constant)):
                    keys.add(node.args[0].value)
        missing = sorted(k for k in keys if k not in i18n.TR)
        self.assertEqual(missing, [])

    def test_switch(self):
        from sublens import i18n
        try:
            i18n.set_lang("tr")
            self.assertEqual(i18n.t("Area: {}", 5), "Alan: 5")
            i18n.set_lang("en")
            self.assertEqual(i18n.t("Area: {}", 5), "Area: 5")
        finally:
            i18n.set_lang("en")


class TestConfig(unittest.TestCase):
    def test_v1_migration(self):
        old = {"engine_key": "lmstudio", "lm_url": "http://localhost:1234", "lm_model": "local-model",
               "deepl_key": "abc:fx", "ocr_psm": "7 - Single line", "region": [1, 2, 300, 400]}
        cfg = config._deep_merge(config.DEFAULTS, config._migrate_v1(old))
        self.assertEqual(cfg["engine"], "openai")
        self.assertEqual(cfg["engines"]["openai"]["base_url"], "http://localhost:1234/v1")
        self.assertEqual(cfg["engines"]["deepl"]["api_key"], "abc:fx")
        self.assertEqual(cfg["engines"]["claude"]["model"], "claude-opus-5-5")


class TestUpdates(unittest.TestCase):
    def test_version_compare(self):
        from sublens import updates
        self.assertTrue(updates.is_newer("v2.3.1", "2.3.0"))
        self.assertTrue(updates.is_newer("3.0", "2.9.9"))
        self.assertFalse(updates.is_newer("v2.3.0", "2.3.0"))
        self.assertFalse(updates.is_newer("2.3", "2.3.0"))
        self.assertFalse(updates.is_newer("1.0", "2.3.0"))     # the old v1 tag
        self.assertFalse(updates.is_newer("nightly", "2.3.0"))

    def test_release_info_prefers_the_exe(self):
        from sublens import updates
        info = updates.release_info({
            "tag_name": "v2.4.0", "body": "notes", "html_url": "https://github.com/x/r/1",
            "assets": [{"name": "SubLens.exe", "browser_download_url": "https://dl/SubLens.exe"}]})
        self.assertEqual((info["version"], info["download"]), ("2.4.0", "https://dl/SubLens.exe"))
        self.assertEqual(updates.release_info({"tag_name": "v2.4.0"})["download"],
                         updates.RELEASES)


if __name__ == "__main__":
    unittest.main()
