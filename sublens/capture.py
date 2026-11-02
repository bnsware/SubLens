"""Screen capture (mss, Pillow fallback) and cheap frame-change detection."""
from __future__ import annotations

import threading

import numpy as np
from PIL import Image, ImageGrab

try:
    import mss
    HAS_MSS = True
except Exception:  # pragma: no cover
    HAS_MSS = False


class Grabber:
    """Thread-safe grabber. Regions are in physical screen pixels."""

    def __init__(self):
        self._local = threading.local()

    def _sct(self):
        s = getattr(self._local, "sct", None)
        if s is None and HAS_MSS:
            ctor = getattr(mss, "MSS", None) or mss.mss  # mss>=10 renamed the class
            s = ctor()
            self._local.sct = s
        return s

    def grab(self, region) -> Image.Image:
        x1, y1, x2, y2 = (int(v) for v in region)
        if HAS_MSS:
            try:
                shot = self._sct().grab({"left": x1, "top": y1,
                                         "width": x2 - x1, "height": y2 - y1})
                return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            except Exception:
                pass
        try:
            return ImageGrab.grab(bbox=(x1, y1, x2, y2), all_screens=True)
        except TypeError:
            return ImageGrab.grab(bbox=(x1, y1, x2, y2))


GRABBER = Grabber()


def frame_signature(img: Image.Image) -> np.ndarray:
    """Tiny grayscale thumbnail; comparing two of these costs microseconds."""
    w, h = img.size
    tw = 128
    th = max(8, min(48, int(tw * h / max(1, w))))
    return np.asarray(img.convert("L").resize((tw, th), Image.BILINEAR), dtype=np.int16)


def frame_changed(a: np.ndarray | None, b: np.ndarray | None, threshold: float = 1.5) -> bool:
    if a is None or b is None or a.shape != b.shape:
        return True
    diff = np.abs(a - b)
    # mean catches fades; the share of strongly changed pixels catches a new short line
    return float(diff.mean()) > threshold or float((diff > 40).mean()) > 0.004
