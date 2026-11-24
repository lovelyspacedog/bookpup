"""Short-lived signed download tokens for e-reader sideload (owner-scoped)."""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

from . import core
from .json_atomic import atomic_write_json

DEFAULT_TTL_SECONDS = 3600
_MAX_ACTIVE_PER_OWNER = 30
_lock = threading.Lock()
_TOKEN_FILE = core.CONFIG_DIR / "sideload_tokens.json"


def _load() -> dict:
    if not _TOKEN_FILE.is_file():
        return {"tokens": []}
    try:
        data = json.loads(_TOKEN_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"tokens": []}
    data.setdefault("tokens", [])
    return data


def _save(data: dict) -> None:
    core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_TOKEN_FILE, data)
    try:
        import os

        os.chmod(_TOKEN_FILE, 0o600)
    except OSError:
        pass


def _purge(data: dict, *, now: float | None = None) -> None:
    t = now if now is not None else time.time()
    tokens = data.get("tokens") or []
    data["tokens"] = [row for row in tokens if float(row.get("expires") or 0) > t]


def create_token(owner: str, item_id: str, delivery: str, *, ttl: int | None = None) -> dict:
    owner = str(owner or "").strip()
    item_id = str(item_id or "").strip()
    delivery = str(delivery or "").strip().lower()
    if not owner or not item_id:
        raise ValueError("Invalid sideload token request")
    secs = int(ttl if ttl is not None else DEFAULT_TTL_SECONDS)
    secs = max(300, min(secs, 24 * 3600))
    token = secrets.token_urlsafe(32)
    expires = time.time() + secs
    with _lock:
        data = _load()
        _purge(data)
        active = [r for r in data["tokens"] if str(r.get("owner")) == owner]
        if len(active) >= _MAX_ACTIVE_PER_OWNER:
            raise ValueError("Too many active download links — wait for one to expire")
        data["tokens"].append(
            {
                "token": token,
                "owner": owner,
                "item_id": item_id,
                "delivery": delivery,
                "expires": expires,
            }
        )
        _save(data)
    return {"token": token, "expires": expires, "expires_in_seconds": secs}


def consume_token(token: str) -> dict | None:
    raw = str(token or "").strip()
    if not raw:
        return None
    with _lock:
        data = _load()
        _purge(data)
        hit = None
        rest = []
        for row in data.get("tokens") or []:
            if secrets.compare_digest(str(row.get("token") or ""), raw):
                hit = row
            else:
                rest.append(row)
        if hit is None:
            _save(data)
            return None
        data["tokens"] = rest
        _save(data)
        return dict(hit)


def peek_token(token: str) -> dict | None:
    raw = str(token or "").strip()
    if not raw:
        return None
    now = time.time()
    with _lock:
        data = _load()
        for row in data.get("tokens") or []:
            if secrets.compare_digest(str(row.get("token") or ""), raw):
                if float(row.get("expires") or 0) <= now:
                    return None
                return dict(row)
    return None