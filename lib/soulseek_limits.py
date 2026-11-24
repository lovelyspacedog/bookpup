"""Per-user Soulseek usage caps (persisted)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from . import accounts
from . import core
from . import jobs
from .core import DEFAULT_SOULSEEK_LIMITS, load_config
from .json_atomic import atomic_write_json

_lock = threading.Lock()
_USAGE_FILE = core.CONFIG_DIR / "soulseek_usage.json"

SEARCH_WINDOW = 3600
DOWNLOAD_WINDOW = 86400


class SoulseekLimitError(PermissionError):
    """Cap exceeded; carries limits snapshot for API responses."""

    def __init__(self, message: str, *, limits: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.limits = limits or {}


def _usage_path() -> Path:
    return _USAGE_FILE


def _load_usage() -> dict[str, Any]:
    path = _usage_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_usage(data: dict[str, Any]) -> None:
    core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    atomic_write_json(_usage_path(), data)


def _global_limits() -> dict[str, int]:
    cfg = load_config().get("soulseek_limits")
    if not isinstance(cfg, dict):
        return dict(DEFAULT_SOULSEEK_LIMITS)
    out = dict(DEFAULT_SOULSEEK_LIMITS)
    for key in out:
        if key in cfg:
            try:
                out[key] = max(0, int(cfg[key]))
            except (TypeError, ValueError):
                pass
    return out


def _user_limits(username: str) -> dict[str, int]:
    base = _global_limits()
    row = accounts.get_user(username) or {}
    over = row.get("soulseek_limits")
    if not isinstance(over, dict):
        return base
    for key in base:
        if key in over:
            try:
                base[key] = max(0, int(over[key]))
            except (TypeError, ValueError):
                pass
    return base


def _prune(times: list[float], window: float, now: float) -> list[float]:
    cutoff = now - window
    return [t for t in times if t >= cutoff]


def _user_bucket(data: dict[str, Any], username: str) -> dict[str, list[float]]:
    users = data.setdefault("users", {})
    if not isinstance(users, dict):
        users = {}
        data["users"] = users
    bucket = users.get(username)
    if not isinstance(bucket, dict):
        bucket = {"searches": [], "downloads": []}
        users[username] = bucket
    if not isinstance(bucket.get("searches"), list):
        bucket["searches"] = []
    if not isinstance(bucket.get("downloads"), list):
        bucket["downloads"] = []
    return bucket


def count_running_soulseek_downloads() -> int:
    n = 0
    for job in jobs.list_jobs():
        if job.get("type") != "download":
            continue
        if str(job.get("download_kind") or "").lower() != "soulseek":
            continue
        if job.get("state") in ("queued", "running"):
            n += 1
    return n


def limits_for_user(username: str) -> dict[str, Any]:
    name = str(username or "").strip()
    caps = _user_limits(name)
    admin = accounts.is_admin(name)
    now = time.time()
    with _lock:
        data = _load_usage()
        bucket = _user_bucket(data, name)
        searches = _prune(list(bucket.get("searches") or []), SEARCH_WINDOW, now)
        downloads = _prune(list(bucket.get("downloads") or []), DOWNLOAD_WINDOW, now)
    search_cap = caps["searches_per_hour"]
    dl_cap = caps["downloads_per_day"]
    household_cap = caps["concurrent_downloads"]
    running = count_running_soulseek_downloads()
    return {
        "searches_per_hour": search_cap,
        "searches_used": len(searches),
        "searches_remaining": None if admin else max(0, search_cap - len(searches)),
        "downloads_per_day": dl_cap,
        "downloads_used": len(downloads),
        "downloads_remaining": None if admin else max(0, dl_cap - len(downloads)),
        "concurrent_downloads": household_cap,
        "concurrent_soulseek_running": running,
        "concurrent_slots_remaining": max(0, household_cap - running),
        "admin_exempt": admin,
    }


def assert_search_allowed(username: str) -> None:
    name = str(username or "").strip()
    if not name or accounts.is_admin(name):
        return
    caps = _user_limits(name)
    lim = limits_for_user(name)
    if int(lim.get("searches_used") or 0) >= caps["searches_per_hour"]:
        raise SoulseekLimitError(
            f"Soulseek sniff cap reached ({caps['searches_per_hour']}/hour). Try again later.",
            limits=lim,
        )


def record_search(username: str) -> None:
    name = str(username or "").strip()
    if not name or accounts.is_admin(name):
        return
    now = time.time()
    with _lock:
        data = _load_usage()
        bucket = _user_bucket(data, name)
        searches = _prune(list(bucket.get("searches") or []), SEARCH_WINDOW, now)
        searches.append(now)
        bucket["searches"] = searches
        _save_usage(data)


def assert_download_allowed(username: str) -> None:
    name = str(username or "").strip()
    if not name or accounts.is_admin(name):
        assert_household_download_slot()
        return
    caps = _user_limits(name)
    lim = limits_for_user(name)
    if int(lim.get("downloads_used") or 0) >= caps["downloads_per_day"]:
        raise SoulseekLimitError(
            f"Soulseek fetch cap reached ({caps['downloads_per_day']}/day). Try again tomorrow.",
            limits=lim,
        )
    assert_household_download_slot()


def record_download(username: str) -> None:
    name = str(username or "").strip()
    if not name or accounts.is_admin(name):
        return
    now = time.time()
    with _lock:
        data = _load_usage()
        bucket = _user_bucket(data, name)
        downloads = _prune(list(bucket.get("downloads") or []), DOWNLOAD_WINDOW, now)
        downloads.append(now)
        bucket["downloads"] = downloads
        _save_usage(data)


def assert_household_download_slot() -> None:
    caps = _global_limits()
    max_c = caps["concurrent_downloads"]
    running = count_running_soulseek_downloads()
    if running >= max_c:
        raise SoulseekLimitError(
            f"Household Soulseek fetch limit ({max_c} at a time). Wait for a slot.",
            limits={"concurrent_soulseek_running": running, "concurrent_downloads": max_c},
        )