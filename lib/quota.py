"""Per-user library size cap enforcement."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path

from . import accounts
from . import user_paths

_lock_guard = threading.Lock()
_user_locks: dict[str, threading.Lock] = {}


def _lock_for(username: str) -> threading.Lock:
    name = str(username or "").strip()
    with _lock_guard:
        lock = _user_locks.get(name)
        if lock is None:
            lock = threading.Lock()
            _user_locks[name] = lock
        return lock


@contextmanager
def storage_transaction(username: str | None = None):
    """Serialize quota check + write for one account."""
    name = username or user_paths.current_user()
    with _lock_for(name):
        yield name


def dir_bytes(root: Path) -> int:
    total = 0
    if not root.is_dir():
        return 0
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def library_usage_for(username: str) -> dict:
    cap = accounts.quota_bytes(username)
    used = dir_bytes(user_paths.library_dir(username))
    used += dir_bytes(user_paths.covers_dir(username))
    used += dir_bytes(user_paths.derived_dir(username))
    return {
        "used_bytes": used,
        "quota_bytes": cap,
        "remaining_bytes": max(0, cap - used),
        "full": used >= cap,
        "username": username,
    }


def library_usage() -> dict:
    return library_usage_for(user_paths.current_user())


def assert_can_store(extra_bytes: int, username: str | None = None) -> None:
    name = username or user_paths.current_user()
    usage = library_usage_for(name)
    if usage["used_bytes"] + extra_bytes > usage["quota_bytes"]:
        cap_gb = usage["quota_bytes"] / (1024**3)
        raise ValueError(f"Library quota exceeded ({cap_gb:.1f} GB cap for {name})")