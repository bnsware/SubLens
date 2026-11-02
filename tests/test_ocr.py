"""OCR tests on synthetic game frames. Windows OCR tests skip where it is unavailable."""
import random
import unittest

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from sublens.ocr import Reader, isolate_bright_text
from sublens.textproc import similarity

LINE1 = "I told you we should have waited for"
LINE2 = "the others before crossing the bridge."
FULL = LINE1 + " " + LINE2


def _font(size):
    for name in ("segoeuib.ttf", "arialbd.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def busy_background(w, h, seed=1):
    """Bright, noisy city/sky-like background - the case v1 failed on."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (w, h), (170, 190, 215))
    d = ImageDraw.Draw(img)
    for _ in range(90):
        x, y = rnd.randrange(w), rnd.randrange(h)
        c = tuple(rnd.randrange(90, 256) for _ in range(3))
        d.rectangle([x, y, x + rnd.randrange(10, 140), y + rnd.randrange(5, 60)], fill=c)
    return img.filter(ImageFilter.GaussianBlur(2))


def draw_subtitle(img, lines, size=26, outline=False, shadow=True):
    d = ImageDraw.Draw(img)
    f = _font(size)
    y = 12
    for text in lines:
        tw = d.textlength(text, font=f)
        x = (img.width - tw) / 2
        if shadow:
            sh = Image.new("L", img.size, 0)
            ImageDraw.Draw(sh).text((x + 2, y + 2), text, font=f, fill=255)
            sh = sh.filter(ImageFilter.GaussianBlur(2))
            img.paste((10, 10, 10), mask=sh)
        if outline:
            d.text((x, y), text, font=f, fill=(255, 255, 255), stroke_width=2,
                   stroke_fill=(0, 0, 0))
        else:
            d.text((x, y), text, font=f, fill=(250, 250, 250))
        y += int(size * 1.45)
    return img


def draw_button_icon(img, x, y, label="X"):
    d = ImageDraw.Draw(img)
    d.ellipse([x, y, x + 30, y + 30], fill=(60, 120, 230), outline=(255, 255, 255), width=2)
    d.text((x + 9, y + 3), label, font=_font(20), fill=(255, 255, 255))


class TestBrightTextFilter(unittest.TestCase):
    def test_output_is_binary_black_on_white(self):
        img = draw_subtitle(busy_background(700, 90), [LINE1])
        out = isolate_bright_text(img).convert("L")
        hist = out.histogram()
        self.assertEqual(sum(hist[1:255]), 0)
        self.assertGreater(hist[255], hist[0])  # mostly background


@unittest.skipUnless(Reader().windows.available and Reader().windows.supports("English"),
                     "Windows OCR (English) not available")
class TestWindowsOcr(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reader = Reader()

    def read(self, img, style):
        return self.reader.read(img, "English", style=style).text

    def test_two_line_subtitle_on_busy_background_reads_as_one_sentence(self):
        img = draw_subtitle(busy_background(760, 100), [LINE1, LINE2])
        best = max((self.read(img, s) for s in ("auto", "subtitle")),
                   key=lambda t: similarity(t, FULL))
        self.assertNotIn("\n", best)
        self.assertGreater(similarity(best, FULL), 0.9, best)

    def test_subtitle_filter_handles_outlined_text(self):
        img = draw_subtitle(busy_background(760, 100, seed=7), [LINE1, LINE2],
                            outline=True, shadow=False)
        text = self.read(img, "subtitle")
        self.assertGreater(similarity(text, FULL), 0.9, text)

    def test_button_icon_not_in_text(self):
        img = Image.new("RGB", (760, 60), (25, 25, 30))
        img = draw_subtitle(img, ["Skip the cutscene"], shadow=False)
        draw_button_icon(img, 150, 12, "X")
        text = self.read(img, "auto")
        self.assertEqual(text.strip(), "Skip the cutscene")


if __name__ == "__main__":
    unittest.main()
