"""Online metadata search (Calibre-like: ISBN first, then title/author)."""

from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from typing import Any

from .core import VERSION, public_base_url
from .covers import COVER_MAX_BYTES

ISBN_RE = re.compile(r"[^0-9Xx]")


def user_agent() -> str:
    return f"BookPup/{VERSION} (household library; +{public_base_url()})"


def _norm_isbn(raw: str | None) -> str | None:
    if not raw:
        return None
    cleaned = ISBN_RE.sub("", str(raw).strip())
    if len(cleaned) in (10, 13):
        return cleaned.upper()
    return None


def _http_json(url: str, timeout: float = 25.0) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _google_query(title: str | None, authors: str | None, isbn: str | None) -> str | None:
    if isbn:
        return "isbn:" + isbn
    parts: list[str] = []
    if title:
        for tok in title.split():
            tok = tok.strip()
            if len(tok) > 1:
                parts.append("intitle:" + tok)
    if authors:
        first = authors.split("&")[0].split(",")[0].strip()
        if first:
            last = first.split()[-1]
            if len(last) > 1:
                parts.append("inauthor:" + last)
    return "+".join(parts) if parts else None


def _from_google_volume(vol: dict) -> dict | None:
    info = vol.get("volumeInfo") or {}
    title = str(info.get("title") or "").strip()
    if not title:
        return None
    authors = info.get("authors") or []
    pub = str(info.get("publishedDate") or "")[:10]
    desc = str(info.get("description") or "").strip()
    if len(desc) > 4000:
        desc = desc[:3997] + "..."
    isbns = []
    for ident in info.get("industryIdentifiers") or []:
        if ident.get("type", "").upper().startswith("ISBN"):
            n = _norm_isbn(ident.get("identifier"))
            if n:
                isbns.append(n)
    cover = None
    links = info.get("imageLinks") or {}
    for key in ("thumbnail", "smallThumbnail"):
        if links.get(key):
            cover = str(links[key]).replace("http://", "https://")
            break
    tags = []
    for cat in info.get("categories") or []:
        tags.extend(str(cat).split(" / "))
    return {
        "source": "google",
        "source_id": str(vol.get("id") or ""),
        "title": title,
        "authors": " & ".join(str(a).strip() for a in authors if a),
        "publisher": str(info.get("publisher") or "").strip(),
        "pubdate": pub,
        "isbn": isbns[0] if isbns else "",
        "tags": ", ".join(dict.fromkeys(t.strip() for t in tags if t.strip())),
        "comments": desc,
        "cover_url": cover or "",
    }


def _search_google(title: str | None, authors: str | None, isbn: str | None) -> list[dict]:
    q = _google_query(title, authors, isbn)
    if not q:
        return []
    url = "https://www.googleapis.com/books/v1/volumes?" + urllib.parse.urlencode(
        {"q": q, "maxResults": 15, "printType": "books"}
    )
    try:
        data = _http_json(url)
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    items = data.get("items") or []
    out: list[dict] = []
    for vol in items:
        row = _from_google_volume(vol)
        if row:
            out.append(row)
    return out


def _search_openlibrary(title: str | None, authors: str | None, isbn: str | None) -> list[dict]:
    params: dict[str, str] = {"limit": "15"}
    if isbn:
        params["isbn"] = isbn
    else:
        if title:
            params["title"] = title
        if authors:
            params["author"] = authors.split("&")[0].split(",")[0].strip()
    if len(params) <= 1 and not isbn:
        return []
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)
    try:
        data = _http_json(url)
    except (OSError, json.JSONDecodeError, ValueError):
        return []
    out: list[dict] = []
    for doc in data.get("docs") or []:
        t = str(doc.get("title") or "").strip()
        if not t:
            continue
        auth = doc.get("author_name") or []
        pubnames = doc.get("publisher") or []
        year = doc.get("first_publish_year")
        pubdate = str(year) if year else ""
        isbns = doc.get("isbn") or []
        isbn_norm = ""
        for raw in isbns:
            isbn_norm = _norm_isbn(raw) or ""
            if isbn_norm:
                break
        cover = ""
        cover_id = doc.get("cover_i")
        if cover_id:
            cover = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"
        elif isbn_norm:
            cover = f"https://covers.openlibrary.org/b/isbn/{isbn_norm}-L.jpg"
        out.append(
            {
                "source": "openlibrary",
                "source_id": str(doc.get("key") or ""),
                "title": t,
                "authors": " & ".join(str(a) for a in auth[:4]),
                "publisher": str(pubnames[0]) if pubnames else "",
                "pubdate": pubdate,
                "isbn": isbn_norm,
                "tags": ", ".join(str(x) for x in (doc.get("subject") or [])[:8]),
                "comments": "",
                "cover_url": cover,
            }
        )
    return out


def _dedupe_key(row: dict) -> str:
    isbn = _norm_isbn(row.get("isbn")) or ""
    if isbn:
        return "isbn:" + isbn
    title = str(row.get("title") or "").lower()[:80]
    auth = str(row.get("authors") or "").lower()[:40]
    return title + "|" + auth


def search_metadata(
    title: str | None = None,
    authors: str | None = None,
    isbn: str | None = None,
) -> list[dict]:
    """Return merged metadata candidates (Google Books + Open Library)."""
    isbn_n = _norm_isbn(isbn)
    title = (title or "").strip() or None
    authors = (authors or "").strip() or None
    if not isbn_n and not title and not authors:
        raise ValueError("title, author, or ISBN required")
    seen: set[str] = set()
    merged: list[dict] = []
    for row in _search_google(title, authors, isbn_n) + _search_openlibrary(title, authors, isbn_n):
        key = _dedupe_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append(row)
    return merged[:20]


def fetch_cover_bytes(url: str, max_bytes: int = COVER_MAX_BYTES) -> bytes:
    from .covers import detect_format
    from .url_safety import assert_fetchable_https_url

    url = assert_fetchable_https_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError("Cover image too large")
    if len(data) < 64:
        raise ValueError("Cover image empty")
    detect_format(data)
    return data