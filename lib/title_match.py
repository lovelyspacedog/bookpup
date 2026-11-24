"""Fuzzy title matching for IRC search vs library catalog."""

from __future__ import annotations

import re

_NORM_RE = re.compile(r"[^a-z0-9]+")

STOP_WORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "to",
        "for",
        "on",
        "at",
        "by",
        "with",
        "from",
        "vol",
        "volume",
        "book",
        "books",
        "edition",
        "ed",
        "part",
        "pt",
        "no",
        "nr",
        "#",
        "pdf",
        "epub",
        "mobi",
        "azw3",
        "cbz",
        "cbr",
        "cb7",
        "fb2",
        "djvu",
        "chm",
        "rtf",
        "lit",
        "md",
        "html",
        "txt",
        "retail",
        "repack",
        "fixed",
        "ret",
    }
)

_FMT_TAIL = re.compile(
    r"\s+(?:epub|pdf|mobi|azw3?|cbz|cbr|cb7|txt|prc|fb2|djvu|chm|rtf|lit|md|html?)(?:\s|$)",
    re.I,
)


def norm_title(text: str) -> str:
    s = (text or "").lower()
    s = _FMT_TAIL.sub(" ", s)
    s = _NORM_RE.sub(" ", s).strip()
    return re.sub(r"\s+", " ", s)


def significant_tokens(text: str) -> list[str]:
    n = norm_title(text)
    out: list[str] = []
    for tok in n.split():
        if len(tok) < 3:
            continue
        if tok in STOP_WORDS:
            continue
        if tok.isdigit():
            continue
        out.append(tok)
    return out


def titles_likely_same(a: str, b: str) -> bool:
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return False
    if na == nb:
        return True

    sig_a = significant_tokens(a)
    sig_b = significant_tokens(b)
    if not sig_a or not sig_b:
        return na == nb

    set_a = set(sig_a)
    set_b = set(sig_b)
    shared = set_a & set_b
    if not shared:
        return False

    min_side = min(len(set_a), len(set_b))
    need = max(2, int(0.65 * min_side + 0.49))
    if len(shared) < need:
        return False

    longest_shared = max(len(t) for t in shared)
    if longest_shared < 5:
        if not (len(shared) >= 2 and set_a <= set_b and set_b <= set_a):
            return False

    if min_side >= 4 and len(shared) < int(0.5 * min_side + 0.51):
        return False

    return True


def match_library_title(irc_title: str, items: list[dict]) -> dict | None:
    best: dict | None = None
    best_score = 0
    for row in items:
        title = str(row.get("title") or "")
        if not titles_likely_same(irc_title, title):
            authors = str(row.get("authors") or "")
            combined = f"{title} {authors}".strip()
            if not authors or not titles_likely_same(irc_title, combined):
                continue
        sig_i = set(significant_tokens(irc_title))
        sig_l = set(significant_tokens(title))
        score = len(sig_i & sig_l) * 10 + max((len(t) for t in sig_i & sig_l), default=0)
        if score > best_score:
            best_score = score
            best = row
    return best