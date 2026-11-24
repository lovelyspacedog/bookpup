"""wttr.in one-line weather for US ZIP codes."""

from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request

from .metadata_search import user_agent

_ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")


def normalize_us_zip(raw: str | None) -> str | None:
    s = str(raw or "").strip()
    if not _ZIP_RE.match(s):
        return None
    return s[:5]


def fetch_wttr_line(zip5: str) -> str:
    loc = urllib.parse.quote(zip5, safe="")
    url = f"https://wttr.in/{loc}?format=3"
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    with urllib.request.urlopen(req, timeout=12) as resp:
        line = resp.read().decode("utf-8", errors="replace").strip().replace("\n", " ")
    if len(line) > 120:
        line = line[:117].rstrip() + "…"
    return line