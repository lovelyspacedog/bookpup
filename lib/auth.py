"""Session tokens (persisted to disk), multi-user."""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from typing import Any

from . import accounts
from . import core

_lock = threading.Lock()
_sessions: dict[str, dict[str, Any]] = {}
SESSION_TTL_SECONDS = 7 * 24 * 3600


def verify_credentials(username: str, password: str) -> bool:
    accounts.migrate_legacy()
    return accounts.verify_password(username, password)


def _persist_unlocked() -> None:
    path = core.SESSIONS_FILE
    core.ensure_dirs()
    payload = {"version": 1, "sessions": dict(_sessions)}
    data = json.dumps(payload, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data)
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def _persist() -> None:
    with _lock:
        _persist_unlocked()


def bootstrap_sessions() -> int:
    """Load non-expired sessions from disk; prune and save. Returns count kept."""
    now = time.time()
    with _lock:
        _sessions.clear()
        path = core.SESSIONS_FILE
        if path.is_file():
            try:
                raw = json.loads(path.read_text())
                rows = raw.get("sessions") if isinstance(raw, dict) else {}
                if isinstance(rows, dict):
                    for token, row in rows.items():
                        if not isinstance(row, dict):
                            continue
                        exp = float(row.get("exp") or 0)
                        if exp <= now:
                            continue
                        user = str(row.get("username") or "").strip()
                        if user:
                            _sessions[str(token)] = {"exp": exp, "username": user}
            except (json.JSONDecodeError, OSError, TypeError, ValueError):
                pass
        expired = [t for t, row in _sessions.items() if float(row.get("exp") or 0) <= now]
        for token in expired:
            _sessions.pop(token, None)
        _persist_unlocked()
        return len(_sessions)


def create_token(username: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = time.time() + SESSION_TTL_SECONDS
    with _lock:
        _sessions[token] = {"exp": expires, "username": str(username).strip()}
        _persist_unlocked()
    return token


def revoke_token(token: str) -> None:
    with _lock:
        if _sessions.pop(token, None) is not None:
            _persist_unlocked()


def set_session_username(token: str, username: str) -> None:
    with _lock:
        row = _sessions.get(token)
        if row:
            row["username"] = str(username).strip()
            _persist_unlocked()


def session_user(header: str | None) -> str | None:
    if not header or not header.startswith("Bearer "):
        return None
    token = header[7:].strip()
    if not token:
        return None
    now = time.time()
    with _lock:
        row = _sessions.get(token)
        if not row:
            return None
        exp = float(row.get("exp") or 0)
        if now > exp:
            _sessions.pop(token, None)
            _persist_unlocked()
            return None
        user = str(row.get("username") or "").strip()
        if not user or not accounts.get_user(user):
            _sessions.pop(token, None)
            _persist_unlocked()
            return None
        if not accounts.get_user(user).get("enabled", True):
            return None
        return user


def check_bearer(header: str | None) -> bool:
    return session_user(header) is not None