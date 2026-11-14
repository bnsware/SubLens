"""New-release check against GitHub. Pure functions + one HTTP call - unit tested."""
from __future__ import annotations

import json
import re
import urllib.request

from . import __version__

REPO = "bnsware/SubLens"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES = f"https://github.com/{REPO}/releases"


def parse_version(tag: str) -> tuple[int, ...]:
    """'v2.3.0' / '2.3' / '1.0' -> (2, 3, 0); anything unreadable -> ()."""
    m = re.match(r"\s*v?(\d+(?:\.\d+)*)", tag or "")
    return tuple(int(p) for p in m.group(1).split(".")) if m else ()


def is_newer(tag: str, current: str = __version__) -> bool:
    new, cur = parse_version(tag), parse_version(current)
    if not new or not cur:
        return False
    width = max(len(new), len(cur))
    return new + (0,) * (width - len(new)) > cur + (0,) * (width - len(cur))


def release_info(data: dict) -> dict:
    """The parts of a GitHub release the app shows: version, notes, page and exe link."""
    exe = next((a.get("browser_download_url") for a in data.get("assets") or []
                if str(a.get("name", "")).lower().endswith(".exe")), None)
    page = data.get("html_url") or RELEASES
    return {"version": str(data.get("tag_name", "")).lstrip("vV"),
            "tag": data.get("tag_name", ""),
            "notes": data.get("body") or "",
            "page": page,
            "download": exe or page}


def latest_release(timeout: float = 8) -> dict:
    """Latest published release. Raises on network/HTTP errors - the caller stays quiet."""
    req = urllib.request.Request(API, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": f"SubLens/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return release_info(json.loads(r.read().decode("utf-8")))
