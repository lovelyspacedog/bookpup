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
    ensure_dirs()
    path = user_paths.reading_state()
    if not path.is_file():
        return {"items": {}}
    return json.loads(path.read_text())


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