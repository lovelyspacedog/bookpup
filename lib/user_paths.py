"""Per-user storage paths and request-scoped current user."""

from __future__ import annotations

import threading
from pathlib import Path

from . import core

_local = threading.Lock()
_current: threading.local = threading.local()


def set_user(username: str | None) -> None:
    if username:
        _current.username = str(username).strip()
    else:
        if hasattr(_current, "username"):
            delattr(_current, "username")


def current_user() -> str:
    u = getattr(_current, "username", None)
    if not u:
        raise RuntimeError("No authenticated user in context")
    return u


def current_user_optional() -> str | None:
    return getattr(_current, "username", None)


def user_root(username: str | None = None) -> Path:
    u = username or current_user()
    return core.CONFIG_DIR / "users" / u


def library_dir(username: str | None = None) -> Path:
    return user_root(username) / "library"


def library_index(username: str | None = None) -> Path:
    return user_root(username) / "library.json"


def covers_dir(username: str | None = None) -> Path:
    return user_root(username) / "covers"


def reading_state(username: str | None = None) -> Path:
    return user_root(username) / "reading.json"


def derived_dir(username: str | None = None) -> Path:
    return user_root(username) / "derived"


def ensure_user_dirs(username: str) -> None:
    root = user_root(username)
    library_dir(username).mkdir(parents=True, exist_ok=True)
    covers_dir(username).mkdir(parents=True, exist_ok=True)
    derived_dir(username).mkdir(parents=True, exist_ok=True)
    idx = library_index(username)
    if not idx.is_file():
        idx.write_text('{\n  "items": []\n}\n')
    rs = reading_state(username)
    if not rs.is_file():
        rs.write_text('{\n  "items": {}\n}\n')