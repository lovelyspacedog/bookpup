"""Whole-kennel share requests and grants between household accounts."""

from __future__ import annotations

import threading
import time
from typing import Any

from . import accounts
from . import core
from . import json_atomic
from . import transfer

SHARES_FILE = core.CONFIG_DIR / "library_shares.json"
_lock = threading.Lock()
_loaded = False
_grants: list[dict[str, Any]] = []
_next_id = 1

ACTIVE_STATUSES = frozenset({"pending", "active"})


def _load_unlocked() -> None:
    global _loaded, _grants, _next_id
    _grants = []
    _next_id = 1
    path = SHARES_FILE
    if path.is_file():
        try:
            import json

            raw = json.loads(path.read_text())
            if isinstance(raw, dict):
                rows = raw.get("grants")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        gid = int(row.get("id") or 0)
                        requester = str(row.get("requester") or "").strip()
                        owner = str(row.get("owner") or "").strip()
                        status = str(row.get("status") or "").strip().lower()
                        if gid < 1 or not requester or not owner or not status:
                            continue
                        mode = row.get("mode")
                        mode_s = str(mode).strip().lower() if mode else None
                        if mode_s not in (None, "", "lend", "give"):
                            mode_s = None
                        if mode_s == "":
                            mode_s = None
                        _grants.append(
                            {
                                "id": gid,
                                "requester": requester,
                                "owner": owner,
                                "status": status,
                                "mode": mode_s,
                                "created_at": float(row.get("created_at") or 0),
                                "responded_at": float(row.get("responded_at") or 0),
                            }
                        )
                _next_id = max(_next_id, int(raw.get("next_id") or 1))
                if _grants:
                    _next_id = max(_next_id, max(int(g["id"]) for g in _grants) + 1)
        except (OSError, ValueError, TypeError):
            pass
    _loaded = True


def _ensure_loaded() -> None:
    with _lock:
        if not _loaded:
            _load_unlocked()


def _persist_unlocked() -> None:
    core.ensure_dirs()
    payload = {
        "version": 1,
        "next_id": _next_id,
        "grants": list(_grants),
    }
    json_atomic.atomic_write_json(SHARES_FILE, payload)


def _find_pair_unlocked(requester: str, owner: str) -> dict[str, Any] | None:
    for row in _grants:
        if row["requester"] == requester and row["owner"] == owner:
            return row
    return None


def get_grant(grant_id: int) -> dict[str, Any]:
    _ensure_loaded()
    with _lock:
        for row in _grants:
            if int(row["id"]) == int(grant_id):
                return dict(row)
    raise KeyError(str(grant_id))


def active_grant(viewer: str, owner: str) -> dict[str, Any] | None:
    who = str(viewer or "").strip()
    dest = str(owner or "").strip()
    if not who or not dest:
        return None
    _ensure_loaded()
    with _lock:
        row = _find_pair_unlocked(who, dest)
        if not row or row.get("status") != "active":
            return None
        return dict(row)


def can_read(viewer: str, owner: str) -> bool:
    grant = active_grant(viewer, owner)
    return grant is not None and grant.get("mode") in ("lend", "give")


def can_take(viewer: str, owner: str) -> bool:
    grant = active_grant(viewer, owner)
    return grant is not None and grant.get("mode") == "give"


def list_for_user(username: str) -> dict[str, list[dict[str, Any]]]:
    who = str(username or "").strip()
    _ensure_loaded()
    incoming: list[dict[str, Any]] = []
    outgoing: list[dict[str, Any]] = []
    browsing: list[dict[str, Any]] = []
    granted: list[dict[str, Any]] = []
    with _lock:
        for row in _grants:
            r = dict(row)
            if r["owner"] == who and r["status"] in ACTIVE_STATUSES:
                incoming.append(r)
            if r["requester"] == who and r["status"] in ACTIVE_STATUSES:
                outgoing.append(r)
            if (
                r["owner"] == who
                and r["status"] == "active"
                and r.get("mode") in ("lend", "give")
            ):
                granted.append(r)
            if (
                r["requester"] == who
                and r["status"] == "active"
                and r.get("mode") in ("lend", "give")
            ):
                browsing.append(
                    {
                        "id": r["id"],
                        "owner": r["owner"],
                        "mode": r["mode"],
                        "responded_at": r.get("responded_at"),
                    }
                )
    incoming.sort(key=lambda x: float(x.get("created_at") or 0), reverse=True)
    outgoing.sort(key=lambda x: float(x.get("created_at") or 0), reverse=True)
    browsing.sort(key=lambda x: str(x.get("owner") or ""))
    return {
        "incoming": incoming,
        "outgoing": outgoing,
        "browsing": browsing,
        "granted": granted,
    }


def create_request(requester: str, owner: str) -> dict[str, Any]:
    transfer._validate_recipient(requester, owner)
    req = str(requester or "").strip()
    own = str(owner or "").strip()
    _ensure_loaded()
    now = time.time()
    global _next_id
    with _lock:
        existing = _find_pair_unlocked(req, own)
        if existing and existing.get("status") in ACTIVE_STATUSES:
            raise ValueError("A pending or active share already exists for this pup")
        if existing:
            existing["status"] = "pending"
            existing["mode"] = None
            existing["created_at"] = now
            existing["responded_at"] = 0
            _persist_unlocked()
            return dict(existing)
        row = {
            "id": _next_id,
            "requester": req,
            "owner": own,
            "status": "pending",
            "mode": None,
            "created_at": now,
            "responded_at": 0,
        }
        _next_id += 1
        _grants.append(row)
        _persist_unlocked()
        return dict(row)


def accept_grant(grant_id: int, owner: str, mode: str) -> dict[str, Any]:
    mode_s = str(mode or "").strip().lower()
    if mode_s not in ("lend", "give"):
        raise ValueError('mode must be "lend" or "give"')
    who = str(owner or "").strip()
    _ensure_loaded()
    now = time.time()
    with _lock:
        row = next((g for g in _grants if int(g["id"]) == int(grant_id)), None)
        if not row:
            raise KeyError(str(grant_id))
        if row["owner"] != who:
            raise PermissionError("Forbidden")
        if row.get("status") != "pending":
            raise ValueError("Share request is not pending")
        row["status"] = "active"
        row["mode"] = mode_s
        row["responded_at"] = now
        _persist_unlocked()
        return dict(row)


def decline_grant(grant_id: int, owner: str) -> dict[str, Any]:
    who = str(owner or "").strip()
    _ensure_loaded()
    now = time.time()
    with _lock:
        row = next((g for g in _grants if int(g["id"]) == int(grant_id)), None)
        if not row:
            raise KeyError(str(grant_id))
        if row["owner"] != who:
            raise PermissionError("Forbidden")
        if row.get("status") != "pending":
            raise ValueError("Share request is not pending")
        row["status"] = "declined"
        row["mode"] = None
        row["responded_at"] = now
        _persist_unlocked()
        return dict(row)


def revoke_grant(grant_id: int, actor: str, *, is_admin: bool) -> dict[str, Any]:
    who = str(actor or "").strip()
    _ensure_loaded()
    now = time.time()
    with _lock:
        row = next((g for g in _grants if int(g["id"]) == int(grant_id)), None)
        if not row:
            raise KeyError(str(grant_id))
        if row.get("status") != "active":
            raise ValueError("Share is not active")
        if row["owner"] != who and not is_admin:
            raise PermissionError("Forbidden")
        row["status"] = "revoked"
        row["mode"] = None
        row["responded_at"] = now
        _persist_unlocked()
        return dict(row)


def cancel_request(grant_id: int, requester: str) -> dict[str, Any]:
    who = str(requester or "").strip()
    _ensure_loaded()
    with _lock:
        row = next((g for g in _grants if int(g["id"]) == int(grant_id)), None)
        if not row:
            raise KeyError(str(grant_id))
        if row["requester"] != who:
            raise PermissionError("Forbidden")
        if row.get("status") != "pending":
            raise ValueError("Only pending requests can be cancelled")
        _grants.remove(row)
        _persist_unlocked()
        return dict(row)


def reload_for_tests() -> None:
    """Reset in-memory cache (tests only)."""
    global _loaded
    with _lock:
        _loaded = False