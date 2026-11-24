"""In-memory login attempt throttle (per client IP)."""

from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_failures: dict[str, list[float]] = {}

MAX_FAILURES = 8
WINDOW_SECONDS = 15 * 60


def _client_key(ip: str | None) -> str:
    return str(ip or "unknown").strip() or "unknown"


def _prune(times: list[float], now: float) -> list[float]:
    cutoff = now - WINDOW_SECONDS
    return [t for t in times if t >= cutoff]


def check_allowed(ip: str | None) -> tuple[bool, int]:
    """Return (allowed, retry_after_seconds if blocked)."""
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
    key = _client_key(ip)
    now = time.time()
    with _lock:
        times = _prune(_failures.get(key, []), now)
        times.append(now)
        _failures[key] = times


def record_success(ip: str | None) -> None:
    key = _client_key(ip)
    with _lock:
        _failures.pop(key, None)