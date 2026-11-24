"""Self-service account data wipe (credentials unchanged)."""

from __future__ import annotations

import json
import random
import shutil
from contextlib import contextmanager
import threading
import time
from pathlib import Path
from typing import Any

from . import accounts
from . import core
from . import jobs
from . import library
from . import staging
from . import user_paths
from .import_session import IMPORT_SESSIONS_DIR
from .irc_worker import worker
from .json_atomic import atomic_write_json

CHALLENGE_TTL_SECONDS = 300

# Fixed dictionary — twelve distinct words per challenge (no duplicates).
WIPE_WORDS: tuple[str, ...] = (
    "amber",
    "anchor",
    "autumn",
    "badger",
    "banner",
    "biscuit",
    "boulder",
    "branch",
    "brindle",
    "candle",
    "canyon",
    "cipher",
    "copper",
    "crystal",
    "den",
    "ember",
    "fable",
    "fern",
    "fjord",
    "fossil",
    "galaxy",
    "garden",
    "ginger",
    "granite",
    "harbor",
    "hollow",
    "horizon",
    "hunter",
    "ivory",
    "juniper",
    "kernel",
    "kettle",
    "lantern",
    "meadow",
    "mercury",
    "moss",
    "nebula",
    "nectar",
    "orchard",
    "parcel",
    "pebble",
    "phantom",
    "pillar",
    "plasma",
    "quartz",
    "rabbit",
    "raven",
    "river",
    "saffron",
    "sandal",
    "shadow",
    "silver",
    "summit",
    "thistle",
    "thunder",
    "timber",
    "tunnel",
    "velvet",
    "violet",
    "wander",
    "willow",
    "winter",
    "yellow",
)

_challenge_lock = threading.Lock()
_challenges: dict[str, tuple[str, float]] = {}


def _new_phrase() -> str:
    return " ".join(random.sample(WIPE_WORDS, 12))


def _challenge_key(actor: str, target: str) -> str:
    actor_s = str(actor or "").strip()
    target_s = str(target or "").strip()
    if actor_s == target_s:
        return f"self:{target_s}"
    return f"admin:{actor_s}:{target_s}"


def issue_wipe_challenge(actor: str, target: str) -> str:
    key = _challenge_key(actor, target)
    phrase = _new_phrase()
    with _challenge_lock:
        _challenges[key] = (phrase, time.time() + CHALLENGE_TTL_SECONDS)
    return phrase


def _take_challenge(actor: str, target: str, phrase: str) -> bool:
    key = _challenge_key(actor, target)
    typed = " ".join(str(phrase or "").strip().split())
    with _challenge_lock:
        row = _challenges.get(key)
        if not row:
            return False
        expected, expires = row
        del _challenges[key]
        if time.time() > expires:
            return False
        return typed == expected


@contextmanager
def _as_user(username: str):
    prev = user_paths.current_user_optional()
    user_paths.set_user(username)
    try:
        yield
    finally:
        if prev:
            user_paths.set_user(prev)
        else:
            user_paths.set_user(None)


def _count_import_sessions(username: str) -> int:
    if not IMPORT_SESSIONS_DIR.is_dir():
        return 0
    count = 0
    for path in IMPORT_SESSIONS_DIR.iterdir():
        if not path.is_dir():
            continue
        manifest = path / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("owner") or "") == username:
            count += 1
    return count


def wipe_preview(actor: str, target: str | None = None) -> dict[str, Any]:
    who = str(actor or "").strip()
    name = str(target or who).strip()
    if name != who and not accounts.is_admin(who):
        raise PermissionError("Admin access required")
    if not accounts.get_user(name):
        raise KeyError(name)
    active_jobs = 0
    for job in jobs.list_jobs():
        if str(job.get("owner") or "") != name:
            continue
        if job.get("state") in jobs.QUEUE_ACTIVE:
            active_jobs += 1
    staged_library = 0
    saved_library = 0
    root = user_paths.user_root(name)
    with _as_user(name):
        for row in library.list_items():
            if library.is_staged(row):
                staged_library += 1
            else:
                saved_library += 1

    import_sessions = _count_import_sessions(name)
    has_data = (
        active_jobs > 0
        or staged_library > 0
        or saved_library > 0
        or import_sessions > 0
        or root.is_dir()
    )
    phrase = issue_wipe_challenge(who, name)
    return {
        "phrase": phrase,
        "target": name,
        "warnings": {
            "active_jobs": active_jobs,
            "staged_library": staged_library,
            "catalogued_library": saved_library,
            "import_sessions": import_sessions,
            "has_local_data": has_data,
        },
    }


def _remove_import_sessions(username: str) -> None:
    if not IMPORT_SESSIONS_DIR.is_dir():
        return
    for path in list(IMPORT_SESSIONS_DIR.iterdir()):
        if not path.is_dir():
            continue
        manifest = path / "manifest.json"
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("owner") or "") != username:
            continue
        shutil.rmtree(path, ignore_errors=True)


def _purge_jobs(username: str) -> None:
    for job in list(jobs.list_jobs()):
        if str(job.get("owner") or "") != username:
            continue
        jid = str(job.get("id") or "")
        if job.get("state") in jobs.QUEUE_ACTIVE and jid:
            try:
                jobs.cancel_job(jid)
            except ValueError:
                pass
            try:
                worker.interrupt(jid)
            except OSError:
                pass
        sid = str(job.get("staging_id") or jid or "")
        if sid:
            try:
                shutil.rmtree(staging.staging_dir(sid), ignore_errors=True)
            except ValueError:
                pass
        if jid:
            try:
                jobs._path(jid).unlink(missing_ok=True)
            except OSError:
                pass


def _purge_user_tree(username: str) -> None:
    root = user_paths.user_root(username)
    for sub in ("library", "covers", "derived"):
        path = root / sub
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    for name in ("library.json", "reading.json", "search_workspace.json", "shelves.json"):
        (root / name).unlink(missing_ok=True)
    user_paths.ensure_user_dirs(username)
    atomic_write_json(user_paths.library_index(username), {"items": []})
    atomic_write_json(user_paths.reading_state(username), {"items": {}})
    # Legacy single-user paths (pre-pack roster); drop so migration cannot resurrect ghosts.
    for legacy in (core.CONFIG_DIR / "library.json", core.CONFIG_DIR / "reading.json"):
        legacy.unlink(missing_ok=True)
    legacy_lib = core.CONFIG_DIR / "library"
    if legacy_lib.is_dir():
        shutil.rmtree(legacy_lib, ignore_errors=True)
    legacy_cov = core.CONFIG_DIR / "covers"
    if legacy_cov.is_dir():
        shutil.rmtree(legacy_cov, ignore_errors=True)


def _run_wipe(target: str) -> None:
    name = str(target or "").strip()
    staging_ids: set[str] = set()
    with _as_user(name):
        for row in library.list_items():
            sid = str(row.get("staging_id") or "").strip()
            if sid:
                staging_ids.add(sid)
    _purge_jobs(name)
    _remove_import_sessions(name)
    _purge_user_tree(name)
    for sid in staging_ids:
        try:
            shutil.rmtree(staging.staging_dir(sid), ignore_errors=True)
        except ValueError:
            pass


def wipe_account(
    actor: str,
    *,
    current_password: str,
    phrase: str,
    target: str | None = None,
) -> str:
    who = str(actor or "").strip()
    name = str(target or who).strip()
    if name != who and not accounts.is_admin(who):
        raise PermissionError("Admin access required")
    if not accounts.get_user(name):
        raise KeyError(name)
    if not accounts.verify_password(who, str(current_password or "")):
        raise PermissionError("Current password is incorrect")
    if not _take_challenge(who, name, phrase):
        raise ValueError("Confirmation phrase is invalid or expired. Open wipe again.")
    _run_wipe(name)
    return name