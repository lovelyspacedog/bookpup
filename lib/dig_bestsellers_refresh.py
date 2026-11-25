"""Fetch and cache Dig popular list from config URL."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .core import CONFIG_DIR, load_config, user_agent
from .json_atomic import atomic_write_json
from .url_safety import assert_fetchable_https_url

LIVE_BESTSELLERS_PATH = CONFIG_DIR / "dig-bestsellers-live.json"
REFRESH_STATE_PATH = CONFIG_DIR / "dig-bestsellers-refresh.json"
MAX_ITEMS = 60
MAX_BYTES = 512 * 1024


def validate_bestsellers_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("bestsellers JSON must be an object")
    items_in = data.get("items")
    if not isinstance(items_in, list):
        raise ValueError("bestsellers JSON needs an items array")
    items: list[dict[str, Any]] = []
    for raw in items_in:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "").strip()
        if not title:
            continue
        row: dict[str, Any] = {"title": title}
        authors = str(raw.get("authors") or "").strip()
        if authors:
            row["authors"] = authors
        sniff = str(raw.get("sniff_query") or "").strip()
        if sniff:
            row["sniff_query"] = sniff
        items.append(row)
        if len(items) >= MAX_ITEMS:
            break
    if not items:
        raise ValueError("bestsellers JSON has no valid items")
    out: dict[str, Any] = {
        "updated": str(data.get("updated") or "").strip(),
        "attribution": str(data.get("attribution") or "").strip(),
        "items": items,
    }
    return out


def refresh_state() -> dict[str, Any]:
    if not REFRESH_STATE_PATH.is_file():
        return {}
    try:
        data = json.loads(REFRESH_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_state(patch: dict[str, Any]) -> None:
    state = refresh_state()
    state.update(patch)
    atomic_write_json(REFRESH_STATE_PATH, state, mode=0o600)


def refresh_enabled(cfg: dict | None = None) -> bool:
    cfg = cfg if cfg is not None else load_config()
    if cfg.get("dig_bestsellers_refresh_enabled") is False:
        return False
    url = str(cfg.get("dig_bestsellers_url") or "").strip()
    return bool(url)


def refresh_interval_seconds(cfg: dict | None = None) -> float:
    cfg = cfg if cfg is not None else load_config()
    try:
        hours = float(cfg.get("dig_bestsellers_refresh_hours") or 168)
    except (TypeError, ValueError):
        hours = 168.0
    hours = max(1.0, hours)
    return hours * 3600.0


def record_refresh_failure(message: str) -> None:
    _save_state({"last_error": message[:240], "last_attempt_at": time.time()})


def due_for_refresh(now: float | None = None) -> bool:
    if not refresh_enabled():
        return False
    now = now if now is not None else time.time()
    state = refresh_state()
    last_ok = float(state.get("last_ok_at") or 0)
    if last_ok <= 0:
        return True
    return (now - last_ok) >= refresh_interval_seconds()


def fetch_and_store_bestsellers(url: str | None = None) -> dict[str, Any]:
    from . import dig_picks

    cfg = load_config()
    raw_url = (url or str(cfg.get("dig_bestsellers_url") or "")).strip()
    if not raw_url:
        raise ValueError("dig_bestsellers_url is not set")
    safe_url = assert_fetchable_https_url(raw_url)
    req = urllib.request.Request(safe_url, headers={"User-Agent": user_agent()})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read(MAX_BYTES + 1)
    except urllib.error.URLError as exc:
        _save_state({"last_error": str(exc)[:240], "last_attempt_at": time.time()})
        raise
    if len(body) > MAX_BYTES:
        raise ValueError("bestsellers JSON too large")
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        _save_state({"last_error": f"invalid JSON: {exc}", "last_attempt_at": time.time()})
        raise ValueError("bestsellers response is not JSON") from exc
    payload = validate_bestsellers_payload(data)
    payload["refreshed_at"] = time.strftime("%Y-%m-%d", time.gmtime())
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(LIVE_BESTSELLERS_PATH, payload, mode=0o600)
    dig_picks.invalidate_bestsellers_cache()
    now = time.time()
    _save_state(
        {
            "last_ok_at": now,
            "last_attempt_at": now,
            "last_error": "",
            "source_url": safe_url,
        }
    )
    return {"ok": True, "items": len(payload["items"]), "path": str(LIVE_BESTSELLERS_PATH)}