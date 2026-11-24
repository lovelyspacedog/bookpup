"""Cover image search (DuckDuckGo by default; optional Google CSE)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

from .metadata_search import _norm_isbn, user_agent

CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
DDG_HOME = "https://duckduckgo.com/"
DDG_IMAGES = "https://duckduckgo.com/i.js"
_VQD_RE = (
    re.compile(r"vqd=['\"]([\d-]+)['\"]"),
    re.compile(r"vqd=([\d-]+)"),
)

Result = dict[str, str | int]


def cse_credentials(config: dict) -> tuple[str, str] | None:
    key = os.environ.get("BOOKPUP_GOOGLE_CSE_API_KEY") or str(config.get("google_cse_api_key") or "").strip()
    cx = os.environ.get("BOOKPUP_GOOGLE_CSE_CX") or str(config.get("google_cse_cx") or "").strip()
    if key and cx:
        return key, cx
    return None


def cover_image_search_enabled(_config: dict | None = None) -> bool:
    """UI hint: DuckDuckGo image search needs no API keys."""
    return True


def build_image_query(
    *,
    title: str | None = None,
    authors: str | None = None,
    isbn: str | None = None,
    query: str | None = None,
) -> str:
    if query and query.strip():
        return query.strip()
    parts: list[str] = []
    isbn_n = _norm_isbn(isbn)
    if isbn_n:
        parts.append(isbn_n)
    if title:
        parts.append(title.strip())
    if authors:
        parts.append(authors.split("&")[0].split(",")[0].strip())
    parts.append("book cover")
    return " ".join(p for p in parts if p)


def _normalize_row(
    *,
    url: str,
    thumb: str,
    title: str,
    width: int,
    height: int,
    context_url: str = "",
) -> Result | None:
    if url.startswith("http://"):
        url = "https://" + url[7:]
    if thumb.startswith("http://"):
        thumb = "https://" + thumb[7:]
    if not url.startswith("https://"):
        return None
    if not thumb.startswith("https://"):
        thumb = url
    if width and height and (width < 80 or height < 80):
        return None
    return {
        "url": url,
        "thumbnail_url": thumb,
        "title": title[:200],
        "width": width,
        "height": height,
        "context_url": context_url,
    }


def _ddg_vqd(query: str) -> str:
    url = DDG_HOME + "?" + urllib.parse.urlencode({"q": query})
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise ValueError(f"Image search unreachable: {exc.reason}") from exc
    for pattern in _VQD_RE:
        match = pattern.search(html)
        if match:
            return match.group(1)
    raise ValueError("Image search failed (could not start DuckDuckGo session)")


def _search_duckduckgo(query: str, *, max_results: int = 20) -> list[Result]:
    vqd = _ddg_vqd(query)
    params = {
        "l": "us-en",
        "o": "json",
        "q": query,
        "vqd": vqd,
        "f": ",,,",
        "p": "1",
    }
    url = DDG_IMAGES + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": user_agent(), "Referer": DDG_HOME},
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        raise ValueError(f"Image search failed ({exc.code})") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Image search unreachable: {exc.reason}") from exc
    out: list[Result] = []
    for row in data.get("results") or []:
        link = str(row.get("image") or "").strip()
        if not link:
            continue
        thumb = str(row.get("thumbnail") or link).strip()
        try:
            w = int(row.get("width") or 0)
            h = int(row.get("height") or 0)
        except (TypeError, ValueError):
            w, h = 0, 0
        normed = _normalize_row(
            url=link,
            thumb=thumb,
            title=str(row.get("title") or "").strip(),
            width=w,
            height=h,
            context_url=str(row.get("url") or "").strip(),
        )
        if normed:
            out.append(normed)
        if len(out) >= max_results:
            break
    return out


def _search_google_cse(
    config: dict,
    query: str,
    *,
    max_results: int = 10,
) -> list[Result]:
    creds = cse_credentials(config)
    if not creds:
        return []
    api_key, cx = creds
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "searchType": "image",
        "num": str(min(max_results, 10)),
        "safe": "active",
        "imgSize": "large",
    }
    url = CSE_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode("utf-8", errors="replace"))
            detail = str((payload.get("error") or {}).get("message") or "").strip()
        except (OSError, json.JSONDecodeError, ValueError, TypeError):
            detail = exc.reason or str(exc)
        raise ValueError(f"Google image search failed ({exc.code}): {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise ValueError(f"Google image search unreachable: {exc.reason}") from exc
    out: list[Result] = []
    for row in data.get("items") or []:
        link = str(row.get("link") or "").strip()
        if not link:
            continue
        img = row.get("image") or {}
        thumb = str(img.get("thumbnailLink") or link).strip()
        try:
            w = int(img.get("width") or 0)
            h = int(img.get("height") or 0)
        except (TypeError, ValueError):
            w, h = 0, 0
        normed = _normalize_row(
            url=link,
            thumb=thumb,
            title=str(row.get("title") or "").strip(),
            width=w,
            height=h,
            context_url=str(img.get("contextLink") or "").strip(),
        )
        if normed:
            out.append(normed)
    return out


def search_cover_images(
    config: dict,
    *,
    title: str | None = None,
    authors: str | None = None,
    isbn: str | None = None,
    query: str | None = None,
) -> list[Result]:
    q = build_image_query(title=title, authors=authors, isbn=isbn, query=query)
    if not q:
        raise ValueError("title, author, ISBN, or query required")
    provider = os.environ.get("BOOKPUP_COVER_IMAGE_PROVIDER", "duckduckgo").strip().lower()
    if provider == "google":
        results = _search_google_cse(config, q)
        if not results:
            raise ValueError(
                "Google image search is not configured (google_cse_api_key and google_cse_cx)"
            )
        return results
    return _search_duckduckgo(q)