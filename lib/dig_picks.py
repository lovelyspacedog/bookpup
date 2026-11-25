"""Dig tab: catalog, Open Library, and bundled bestseller picks."""

from __future__ import annotations

import json
import time
from collections import Counter
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .core import CONFIG_DIR
from .dig_bestsellers_refresh import LIVE_BESTSELLERS_PATH
from .library import is_registered, list_registered_items
from .metadata_search import _dedupe_key, _search_openlibrary
from .routes import static_files
from .title_match import titles_likely_same

STATIC_DIR = static_files.STATIC_DIR
BESTSELLERS_PATH = STATIC_DIR / "data" / "dig-bestsellers.json"
CACHE_DIR = CONFIG_DIR / "dig_picks_cache"
CACHE_TTL_SECONDS = 6 * 3600

CATALOG_MAX = 8
OL_MAX = 10
OL_SEARCH_AUTHORS = 3

_bestsellers_mtime: float = 0.0
_bestsellers_data: dict[str, Any] | None = None

OlSearchFn = Callable[[str | None, str | None, str | None], list[dict]]

OL_COVER_CACHE_PATH = CACHE_DIR / "ol_covers.json"
MAX_NEW_COVER_LOOKUPS = 10


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _split_authors(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    out: list[str] = []
    for chunk in text.replace("&", ",").split(","):
        name = chunk.strip()
        if len(name) > 1:
            out.append(name)
    return out


def _split_tags(raw: str) -> list[str]:
    text = (raw or "").strip()
    if not text:
        return []
    return [t.strip() for t in text.split(",") if t.strip()]


def _owned_titles(registered: list[dict]) -> list[str]:
    return [str(row.get("title") or "") for row in registered if row.get("title")]


def in_kennel(title: str, owned: list[str]) -> bool:
    return any(titles_likely_same(title, t) for t in owned)


def _library_cover_url(item_id: str) -> str:
    return "/api/library/" + item_id + "/cover"


def _cover_for_author(registered: list[dict], author: str) -> str | None:
    want = author.strip().lower()
    for row in registered:
        if not row.get("has_cover"):
            continue
        iid = str(row.get("id") or "").strip()
        if not iid:
            continue
        for a in _split_authors(str(row.get("authors") or "")):
            if a.lower() == want:
                return _library_cover_url(iid)
    return None


def _cover_for_series(registered: list[dict], series_key: str) -> str | None:
    want = series_key.strip().lower()
    for row in registered:
        if not row.get("has_cover"):
            continue
        series = str(row.get("series") or "").strip().lower()
        if series != want:
            continue
        iid = str(row.get("id") or "").strip()
        if iid:
            return _library_cover_url(iid)
    return None


def _cover_for_tag(registered: list[dict], tag: str) -> str | None:
    want = tag.strip().lower()
    for row in registered:
        if not row.get("has_cover"):
            continue
        tags = [t.lower() for t in _split_tags(str(row.get("tags") or ""))]
        if want not in tags:
            continue
        iid = str(row.get("id") or "").strip()
        if iid:
            return _library_cover_url(iid)
    return None


def _read_ol_cover_cache() -> dict[str, str]:
    if not OL_COVER_CACHE_PATH.is_file():
        return {}
    try:
        data = json.loads(OL_COVER_CACHE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_ol_cover_cache(cache: dict[str, str]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OL_COVER_CACHE_PATH.write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")


def _ol_cover_for_title(title: str, authors: str, cache: dict[str, str]) -> tuple[str | None, bool]:
    """Return (cover_url, cache_dirty)."""
    key = _dedupe_key({"title": title, "authors": authors, "isbn": ""})
    if key in cache:
        hit = str(cache.get(key) or "").strip()
        return (hit or None, False)
    try:
        rows = _search_openlibrary(title, authors or None, None)
    except OSError:
        rows = []
    url = str(rows[0].get("cover_url") or "").strip() if rows else ""
    cache[key] = url
    return (url or None, True)


def enrich_bestseller_json_items(rows: list[dict], *, max_lookups: int = MAX_NEW_COVER_LOOKUPS) -> None:
    """Fill cover_url on bestseller JSON rows (refresh or bundled file)."""
    stub_items = [
        {
            "title": str(r.get("title") or ""),
            "authors": str(r.get("authors") or ""),
            "cover_url": str(r.get("cover_url") or "").strip() or None,
        }
        for r in rows
    ]
    _attach_bestseller_covers(stub_items, rows, max_lookups=max_lookups)
    for row, stub in zip(rows, stub_items, strict=False):
        url = stub.get("cover_url")
        if url:
            row["cover_url"] = url


def _attach_bestseller_covers(
    items: list[dict], raw_rows: list[dict], *, max_lookups: int = MAX_NEW_COVER_LOOKUPS
) -> None:
    cache = _read_ol_cover_cache()
    dirty = False
    lookups = 0
    for item, raw in zip(items, raw_rows, strict=False):
        preset = str(raw.get("cover_url") or "").strip()
        if preset:
            item["cover_url"] = preset
            continue
        if item.get("cover_url"):
            continue
        key = _dedupe_key(
            {"title": str(item.get("title") or ""), "authors": item.get("authors"), "isbn": ""}
        )
        if key in cache:
            hit = str(cache.get(key) or "").strip()
            if hit:
                item["cover_url"] = hit
            continue
        if lookups >= max_lookups:
            continue
        lookups += 1
        url, changed = _ol_cover_for_title(
            str(item.get("title") or ""),
            str(item.get("authors") or ""),
            cache,
        )
        if changed:
            dirty = True
        if url:
            item["cover_url"] = url
    if dirty:
        _write_ol_cover_cache(cache)


def _pick_item(
    *,
    title: str,
    authors: str,
    sniff_query: str,
    reason: str,
    source: str,
    owned: list[str],
    cover_url: str | None = None,
) -> dict[str, Any]:
    sq = (sniff_query or title).strip()
    return {
        "title": title.strip(),
        "authors": (authors or "").strip(),
        "sniff_query": sq,
        "reason": reason,
        "source": source,
        "in_kennel": in_kennel(title, owned),
        "cover_url": cover_url or None,
    }


def catalog_picks(registered: list[dict]) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    if not registered:
        warnings.append("catalog_empty")
        return [], warnings

    owned = _owned_titles(registered)
    author_counts: Counter[str] = Counter()
    tag_counts: Counter[str] = Counter()
    series_map: dict[str, list[str]] = {}

    for row in registered:
        for auth in _split_authors(str(row.get("authors") or "")):
            author_counts[auth] += 1
        for tag in _split_tags(str(row.get("tags") or "")):
            tag_counts[tag.lower()] += 1
        series = str(row.get("series") or "").strip()
        if series:
            series_map.setdefault(series.lower(), []).append(str(row.get("title") or ""))

    items: list[dict] = []
    seen_q: set[str] = set()

    def add(item: dict[str, Any]) -> None:
        q = str(item.get("sniff_query") or "").lower()
        if not q or q in seen_q:
            return
        seen_q.add(q)
        items.append(item)

    for author, _ in author_counts.most_common(5):
        add(
            _pick_item(
                title=f"More by {author}",
                authors=author,
                sniff_query=author,
                reason=f"Often in your kennel ({author_counts[author]} tagged)",
                source="catalog",
                owned=owned,
                cover_url=_cover_for_author(registered, author),
            )
        )
        if len(items) >= CATALOG_MAX:
            break

    for series_key, titles in sorted(series_map.items(), key=lambda x: -len(x[1])):
        if len(titles) >= 5:
            continue
        label = series_key.title()
        add(
            _pick_item(
                title=f"{label} — next in series?",
                authors="",
                sniff_query=label,
                reason=f"You have {len(titles)} in “{label}”",
                source="catalog",
                owned=owned,
                cover_url=_cover_for_series(registered, series_key),
            )
        )
        if len(items) >= CATALOG_MAX:
            break

    for tag, _ in tag_counts.most_common(4):
        if len(tag) < 3:
            continue
        add(
            _pick_item(
                title=f"More “{tag}” picks",
                authors="",
                sniff_query=tag,
                reason=f"Tag shows up on {tag_counts[tag]} bones",
                source="catalog",
                owned=owned,
                cover_url=_cover_for_tag(registered, tag),
            )
        )
        if len(items) >= CATALOG_MAX:
            break

    return items[:CATALOG_MAX], warnings


def invalidate_bestsellers_cache() -> None:
    global _bestsellers_mtime, _bestsellers_data
    _bestsellers_mtime = 0.0
    _bestsellers_data = None


def _bestsellers_source_path() -> Path:
    if LIVE_BESTSELLERS_PATH.is_file():
        return LIVE_BESTSELLERS_PATH
    return BESTSELLERS_PATH


def _load_bestsellers_file() -> dict[str, Any]:
    global _bestsellers_mtime, _bestsellers_data
    path = _bestsellers_source_path()
    if not path.is_file():
        return {"updated": "", "attribution": "", "items": []}
    mtime = path.stat().st_mtime
    if _bestsellers_data is not None and mtime == _bestsellers_mtime:
        return _bestsellers_data
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        data = {"items": []}
    _bestsellers_data = data
    _bestsellers_mtime = mtime
    return data


def bestseller_picks(owned: list[str]) -> tuple[list[dict], dict[str, str]]:
    data = _load_bestsellers_file()
    meta = {
        "updated": str(data.get("updated") or ""),
        "attribution": str(data.get("attribution") or ""),
    }
    raw_items = data.get("items") or []
    items: list[dict] = []
    raws: list[dict] = []
    for row in raw_items:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if not title:
            continue
        authors = str(row.get("authors") or "").strip()
        sniff = str(row.get("sniff_query") or "").strip() or f"{authors} {title}".strip()
        preset_cover = str(row.get("cover_url") or "").strip() or None
        items.append(
            _pick_item(
                title=title,
                authors=authors,
                sniff_query=sniff,
                reason="Popular on the trail",
                source="bestseller",
                owned=owned,
                cover_url=preset_cover,
            )
        )
        raws.append(row)
    _attach_bestseller_covers(items, raws)
    return items, meta


def _cache_path(username: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in username)
    return CACHE_DIR / f"{safe}.json"


def _read_ol_cache(username: str) -> dict[str, Any] | None:
    path = _cache_path(username)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ts = float(data.get("cached_at") or 0)
    if time.time() - ts > CACHE_TTL_SECONDS:
        return None
    return data


def _write_ol_cache(username: str, items: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"cached_at": time.time(), "items": items}
    path = _cache_path(username)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def openlibrary_picks(
    registered: list[dict],
    owned: list[str],
    username: str,
    *,
    search_fn: OlSearchFn | None = None,
) -> tuple[list[dict], list[str]]:
    warnings: list[str] = []
    cached = _read_ol_cache(username)
    if cached is not None:
        return list(cached.get("items") or []), warnings

    if not registered:
        return [], warnings

    search = search_fn or _search_openlibrary
    author_counts: Counter[str] = Counter()
    for row in registered:
        for auth in _split_authors(str(row.get("authors") or "")):
            author_counts[auth] += 1

    seen: set[str] = set()
    merged: list[dict] = []
    try:
        for author, _ in author_counts.most_common(OL_SEARCH_AUTHORS):
            for doc in search(None, author, None):
                key = _dedupe_key(doc)
                if key in seen:
                    continue
                title = str(doc.get("title") or "").strip()
                if not title or in_kennel(title, owned):
                    continue
                seen.add(key)
                merged.append(doc)
                if len(merged) >= OL_MAX:
                    break
            if len(merged) >= OL_MAX:
                break
    except OSError:
        warnings.append("openlibrary_unavailable")

    items: list[dict] = []
    for doc in merged[:OL_MAX]:
        title = str(doc.get("title") or "").strip()
        authors = str(doc.get("authors") or "").strip()
        sniff = f"{authors} {title}".strip() if authors else title
        items.append(
            _pick_item(
                title=title,
                authors=authors,
                sniff_query=sniff,
                reason="Along the trail (Open Library)",
                source="openlibrary",
                owned=owned,
                cover_url=str(doc.get("cover_url") or "") or None,
            )
        )

    if items:
        _write_ol_cache(username, items)
    elif not warnings:
        warnings.append("openlibrary_empty")

    return items, warnings


def build_dig_picks(username: str, *, search_fn: OlSearchFn | None = None) -> dict[str, Any]:
    registered = [row for row in list_registered_items() if is_registered(row)]
    owned = _owned_titles(registered)
    catalog_items, warnings = catalog_picks(registered)
    ol_items, ol_warn = openlibrary_picks(registered, owned, username, search_fn=search_fn)
    warnings.extend(ol_warn)
    best_items, best_meta = bestseller_picks(owned)

    sections = [
        {
            "id": "catalog",
            "title": "From your kennel",
            "items": catalog_items,
        },
        {
            "id": "openlibrary",
            "title": "Along the trail",
            "items": ol_items,
        },
        {
            "id": "bestsellers",
            "title": "Popular on the trail",
            "items": best_items,
            "meta": best_meta,
        },
    ]

    return {
        "ok": True,
        "generated_at": _now_iso(),
        "sections": sections,
        "warnings": warnings,
    }