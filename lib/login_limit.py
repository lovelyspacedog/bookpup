"""Login attempt throttle (per client IP), persisted across restarts."""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

from . import core
from .json_atomic import atomic_write_json

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}
_loaded = False

MAX_FAILURES = 8
WINDOW_SECONDS = 15 * 60
_FAILURES_FILE = core.CONFIG_DIR / "login_throttle.json"


def _client_key(ip: str | None) -> str:
    return str(ip or "unknown").strip() or "unknown"


def _prune(times: list[float], now: float) -> list[float]:
    cutoff = now - WINDOW_SECONDS
    return [t for t in times if t >= cutoff]


def _persist_unlocked() -> None:
    core.ensure_dirs()
    payload = {"version": 1, "failures": dict(_failures)}
    atomic_write_json(_FAILURES_FILE, payload)
    try:
        os.chmod(_FAILURES_FILE, 0o600)
    except OSError:
        pass


def bootstrap_failures() -> int:
    """Load throttle state from disk; prune expired entries. Returns tracked IP count."""
    global _loaded
    now = time.time()
    with _lock:
        _failures.clear()
        path = _FAILURES_FILE
        if path.is_file():
            try:
                raw = json.loads(path.read_text())
                rows = raw.get("failures") if isinstance(raw, dict) else {}
                if isinstance(rows, dict):
                    for key, times in rows.items():
                        if not isinstance(times, list):
                            continue
                        cleaned = _prune([float(t) for t in times], now)
                        if cleaned:
                            _failures[str(key)] = cleaned
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        _persist_unlocked()
        _loaded = True
        return len(_failures)


def _ensure_loaded() -> None:
    global _loaded
    if not _loaded:
        bootstrap_failures()


def check_allowed(ip: str | None) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds if blocked)."""
    _ensure_loaded()
    key = _client_key(ip)
    now = time.time()
    with _lock:
        times = _prune(_failures.get(key, []), now)
        if len(times) < MAX_FAILURES:
            _failures[key] = times
            return True, 0
        oldest = min(times)
        retry = int(max(1, WINDOW_SECONDS - (now - oldest)))
        _failures[key] = times
        return False, retry


def record_failure(ip: str | None) -> None:
    _ensure_loaded()
    key = _client_key(ip)
    now = time.time()
    with _lock:
        times = _prune(_failures.get(key, []), now)
        times.append(now)
        _failures[key] = times
        _persist_unlocked()


def record_success(ip: str | None) -> None:
    _ensure_loaded()
    key = _client_key(ip)
    with _lock:
        if _failures.pop(key, None) is not None:
            _persist_unlocked()