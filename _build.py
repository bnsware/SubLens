"""SubLens'i PyInstaller ile derler. sublens_exe.bat tarafından çağrılır.

Bat üzerinden uzun komut + boşluklu path kotalarını yönetmek zor olduğu için
PyInstaller programatik olarak buradan çalıştırılır.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def make_icon(path: Path):
    """Same drawing as theme.app_icon: a dark screen with two subtitle-yellow bars."""
    from PIL import Image, ImageDraw
    s = 1024                                  # draw big, let Pillow downscale per size
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    u = s / 64
    d.rounded_rectangle((4 * u, 6 * u, 60 * u, 58 * u), 10 * u, fill="#26272b",
                        outline="#45464c", width=int(1.5 * u))
    d.rounded_rectangle((14 * u, 34 * u, 50 * u, 40 * u), 3 * u, fill="#f2c14e")
    d.rounded_rectangle((20 * u, 44 * u, 44 * u, 50 * u), 3 * u, fill=(242, 193, 78, 150))
    im.save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


def build() -> int:
    ico = ROOT / "SubLens.ico"
    make_icon(ico)
    args = [
        "--name", "SubLens",
        "--onefile",
        "--windowed",
        "--clean",
        "--noconfirm",
        "--icon", str(ROOT / "SubLens.ico"),
        "--hidden-import", "keyboard",
        "--hidden-import", "mss",
        "--hidden-import", "anthropic",
        "--collect-all", "winrt",
        "--collect-submodules", "sublens",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pytest",
        "--exclude-module", "pytesseract",
        "--add-data", f"{ROOT / 'SubLens.ico'}{os.pathsep}.",
    ]
    for name in ("READMEapp.md", "READMEapp.en.md"):
        if (ROOT / name).exists():
            args += ["--add-data", f"{ROOT / name}{os.pathsep}."]
    args.append(str(ROOT / "main.py"))

    print("PyInstaller args:")
    for a in args:
        print(f"  {a}")
    print()

    import PyInstaller.__main__
    PyInstaller.__main__.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(build())
