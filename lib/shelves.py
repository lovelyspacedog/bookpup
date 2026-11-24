"""Per-user custom library shelves."""

from __future__ import annotations

import secrets
import time
from typing import Any

from .json_atomic import atomic_write_json
from . import library
from . import user_paths

SHELF_NAME_MAX = 80


def _index_path() -> Any:
    return user_paths.shelves_index()


def _load() -> dict:
    path = _index_path()
    if not path.is_file():
        return {"shelves": []}
    import json

    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        return {"shelves": []}
    shelves = data.get("shelves")
    if not isinstance(shelves, list):
        return {"shelves": []}
    return {"shelves": shelves}


def _save(data: dict) -> None:
    atomic_write_json(_index_path(), data)


def _registered_ids() -> set[str]:
    return {str(row.get("id") or "") for row in library.list_items() if library.is_registered(row)}


def _prune_item_ids(item_ids: list, registered: set[str]) -> list[str]:
    return [iid for iid in item_ids if iid in registered]


def list_shelves(*, prune: bool = True) -> list[dict]:
    data = _load()
    registered = _registered_ids() if prune else None
    out: list[dict] = []
    fixed_rows: list[dict] = []
    dirty = False
    for row in data.get("shelves") or []:
        if not isinstance(row, dict):
            continue
        stored = dict(row)
        iids = list(stored.get("item_ids") or [])
        if registered is not None:
            pruned = _prune_item_ids(iids, registered)
            if pruned != iids:
                stored["item_ids"] = pruned
                dirty = True
        fixed_rows.append(stored)
        out.append(_public_shelf(stored))
    if dirty:
        _save({"shelves": fixed_rows})
    return out


def _public_shelf(row: dict) -> dict:
    iids = list(row.get("item_ids") or [])
    return {
        "id": str(row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "created_at": row.get("created_at"),
        "item_ids": iids,
        "count": len(iids),
    }


def _find_shelf(data: dict, shelf_id: str) -> tuple[int, dict] | None:
    for idx, row in enumerate(data.get("shelves") or []):
        if isinstance(row, dict) and row.get("id") == shelf_id:
            return idx, row
    return None


def _norm_name(name: str) -> str:
    cleaned = str(name or "").strip()
    if not cleaned:
        raise ValueError("Shelf name required")
    if len(cleaned) > SHELF_NAME_MAX:
        raise ValueError(f"Shelf name too long (max {SHELF_NAME_MAX})")
    return cleaned


def create_shelf(name: str) -> dict:
    data = _load()
    shelf_id = secrets.token_urlsafe(12)
    row = {
        "id": shelf_id,
        "name": _norm_name(name),
        "created_at": time.time(),
        "item_ids": [],
    }
    data.setdefault("shelves", []).append(row)
    _save(data)
    return _public_shelf(row)


def rename_shelf(shelf_id: str, name: str) -> dict:
    data = _load()
    found = _find_shelf(data, shelf_id)
    if not found:
        raise KeyError(shelf_id)
    idx, row = found
    row = {**row, "name": _norm_name(name)}
    data["shelves"][idx] = row
    _save(data)
    return _public_shelf(row)


def delete_shelf(shelf_id: str) -> None:
    data = _load()
    shelves = [r for r in (data.get("shelves") or []) if isinstance(r, dict) and r.get("id") != shelf_id]
    if len(shelves) == len(data.get("shelves") or []):
        raise KeyError(shelf_id)
    data["shelves"] = shelves
    _save(data)


def set_shelf_items(shelf_id: str, item_ids: list) -> dict:
    registered = _registered_ids()
    unique: list[str] = []
    seen: set[str] = set()
    for raw in item_ids or []:
        iid = str(raw or "").strip()
        if not iid or iid in seen:
            continue
        if iid not in registered:
            raise ValueError("Only catalogued books can go on a shelf")
        seen.add(iid)
        unique.append(iid)
    data = _load()
    found = _find_shelf(data, shelf_id)
    if not found:
        raise KeyError(shelf_id)
    idx, row = found
    row = {**row, "item_ids": unique}
    data["shelves"][idx] = row
    _save(data)
    return _public_shelf(row)


def remove_item_from_all_shelves(item_id: str) -> None:
    iid = str(item_id or "").strip()
    if not iid:
        return
    data = _load()
    dirty = False
    shelves = data.get("shelves") or []
    for row in shelves:
        if not isinstance(row, dict):
            continue
        iids = list(row.get("item_ids") or [])
        if iid in iids:
            row["item_ids"] = [x for x in iids if x != iid]
            dirty = True
    if dirty:
        _save(data)