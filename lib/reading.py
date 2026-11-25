"""Per-book reading position and bookmarks (server-side)."""

from __future__ import annotations

import json
import secrets
import time
from pathlib import Path
from typing import Any

from .core import ensure_dirs
from . import user_paths
from .json_atomic import atomic_write_json
from .shared_library import shared_storage_key


def _load() -> dict:
    return _load_for_user(None)


def _load_for_user(username: str | None) -> dict:
    ensure_dirs()
    path = user_paths.reading_state(username)
    if not path.is_file():
        return {"items": {}}
    return json.loads(path.read_text())


_DONE_FRACTION = 0.97


def _fraction_from_location(loc: dict[str, Any] | None) -> float | None:
    if not loc or not isinstance(loc, dict):
        return None
    typ = str(loc.get("type") or "")
    if typ == "epub":
        if loc.get("flow") == "scrolled":
            scroll = loc.get("scroll")
            if scroll is not None:
                return float(scroll)
        pct = loc.get("percentage")
        if pct is not None:
            if isinstance(pct, dict) and pct.get("start") is not None:
                return float(pct["start"])
            return float(pct)
        return None
    if typ in ("txt", "md", "html") and loc.get("scroll") is not None:
        return float(loc["scroll"])
    if typ == "pdf":
        page = loc.get("page")
        total = loc.get("page_count") or loc.get("pages")
        if page is not None and total:
            try:
                return max(0.0, min(1.0, (float(page) - 1) / float(total)))
            except (TypeError, ValueError):
                pass
        return None
    if typ in ("cbz", "cbr", "cb7", "comic"):
        page = loc.get("page")
        total = loc.get("pages")
        if page is not None and total:
            try:
                return max(0.0, min(1.0, float(page) / max(1.0, float(total) - 1)))
            except (TypeError, ValueError):
                pass
        return None
    if typ == "koreader" and loc.get("percentage") is not None:
        return float(loc["percentage"])
    return None


def _progress_label(loc: dict[str, Any] | None) -> str | None:
    if not loc or not isinstance(loc, dict):
        return None
    frac = _fraction_from_location(loc)
    if frac is not None:
        return f"{round(frac * 100)}%"
    typ = str(loc.get("type") or "")
    if typ == "pdf" and loc.get("page"):
        return f"p.{loc['page']}"
    if typ in ("cbz", "cbr", "cb7", "comic") and loc.get("page") is not None:
        return f"p.{int(loc['page']) + 1}"
    return "Started"


def _in_progress_from_location(loc: dict[str, Any] | None) -> bool:
    if not loc:
        return False
    frac = _fraction_from_location(loc)
    if frac is not None:
        return frac < _DONE_FRACTION
    return True


def _row_catalog_summary(row: dict[str, Any]) -> dict[str, Any]:
    loc = row.get("location")
    if not loc:
        return {}
    updated = row.get("updated_at")
    frac = _fraction_from_location(loc) if isinstance(loc, dict) else None
    pct = round(frac * 100) if frac is not None else None
    return {
        "updated_at": updated,
        "progress_pct": pct,
        "progress_label": _progress_label(loc if isinstance(loc, dict) else None),
        "in_progress": _in_progress_from_location(loc if isinstance(loc, dict) else None),
    }


def catalog_summaries(
    viewer: str,
    item_ids: list[str],
    *,
    shared_catalog_owner: str | None = None,
) -> dict[str, dict[str, Any]]:
    if not viewer or not item_ids:
        return {}
    data = _load_for_user(viewer)
    items = data.get("items") or {}
    out: dict[str, dict[str, Any]] = {}
    for iid in item_ids:
        if not iid:
            continue
        key = shared_storage_key(iid, shared_catalog_owner)
        row = items.get(key) or {}
        summary = _row_catalog_summary(row)
        if summary:
            out[iid] = summary
    return out


def _save(data: dict) -> None:
    path = user_paths.reading_state()
    atomic_write_json(path, data)


def get_state(item_id: str, *, shared_owner: str | None = None) -> dict:
    key = shared_storage_key(item_id, shared_owner)
    data = _load()
    row = (data.get("items") or {}).get(key) or {}
    return {
        "item_id": item_id,
        "location": row.get("location"),
        "updated_at": row.get("updated_at"),
        "bookmarks": list(row.get("bookmarks") or []),
    }


def set_location(
    item_id: str, location: dict[str, Any] | None, *, shared_owner: str | None = None
) -> dict:
    if not item_id:
        raise ValueError("item_id required")
    key = shared_storage_key(item_id, shared_owner)
    data = _load()
    items = data.setdefault("items", {})
    row = items.setdefault(key, {"bookmarks": []})
    row["location"] = location
    row["updated_at"] = time.time()
    _save(data)
    return get_state(item_id, shared_owner=shared_owner)


def add_bookmark(
    item_id: str,
    label: str,
    location: dict[str, Any],
    *,
    shared_owner: str | None = None,
) -> dict:
    if not location:
        raise ValueError("location required")
    label = (label or "Bookmark").strip()[:120] or "Bookmark"
    key = shared_storage_key(item_id, shared_owner)
    data = _load()
    items = data.setdefault("items", {})
    row = items.setdefault(key, {"bookmarks": []})
    marks = row.setdefault("bookmarks", [])
    mark = {
        "id": secrets.token_urlsafe(8),
        "label": label,
        "location": location,
        "created_at": time.time(),
    }
    marks.append(mark)
    _save(data)
    return mark


def delete_bookmark(
    item_id: str, bookmark_id: str, *, shared_owner: str | None = None
) -> None:
    key = shared_storage_key(item_id, shared_owner)
    data = _load()
    items = data.get("items") or {}
    row = items.get(key)
    if not row:
        raise KeyError(bookmark_id)
    marks = row.get("bookmarks") or []
    kept = [m for m in marks if m.get("id") != bookmark_id]
    if len(kept) == len(marks):
        raise KeyError(bookmark_id)
    row["bookmarks"] = kept
    _save(data)


def delete_item_state(item_id: str) -> None:
    data = _load()
    items = data.get("items") or {}
    if item_id in items:
        del items[item_id]
        _save(data)