"""Household accounts and per-user library quotas."""

from __future__ import annotations

import json
import re
import secrets
import threading
from pathlib import Path
from typing import Any

from . import core
from .core import LIBRARY_QUOTA_BYTES, load_config
from .json_atomic import atomic_write_json
from .safe_ids import validate_username as _safe_username


def _accounts_file() -> Path:
    return core.CONFIG_DIR / "accounts.json"
_lock = threading.Lock()
_cache: dict | None = None
_cache_mtime: float | None = None

DEFAULT_USER_QUOTA = 2 * 1024 * 1024 * 1024
_KINDLE_SUFFIXES = (
    "@kindle.com",
    "@free.kindle.com",
    "@pbsns.net",
    "@sendtokindle.com",
)


def _load_raw() -> dict:
    global _cache, _cache_mtime
    path = _accounts_file()
    mtime = path.stat().st_mtime if path.is_file() else None
    if _cache is not None and _cache_mtime == mtime:
        return _cache
    if not path.is_file():
        data: dict[str, Any] = {"version": 1, "users": []}
    else:
        data = json.loads(path.read_text())
    data.setdefault("version", 1)
    data.setdefault("users", [])
    _cache = data
    _cache_mtime = mtime
    return data


def _save(data: dict) -> None:
    global _cache, _cache_mtime
    path = _accounts_file()
    atomic_write_json(path, data)
    try:
        _cache_mtime = path.stat().st_mtime
    except OSError:
        _cache_mtime = None
    _cache = data
    try:
        import os

        os.chmod(path, 0o600)
    except OSError:
        pass


def migrate_legacy() -> None:
    """One-time: config.json login → accounts.json; flat library → users/{admin}/."""
    from . import user_paths
    import shutil

    core.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    admin_name = str(cfg.get("username") or "book").strip()
    admin_pass = str(cfg.get("password") or "")

    data = _load_raw()
    if not data["users"]:
        quota = int(cfg.get("library_quota_bytes") or LIBRARY_QUOTA_BYTES)
        data["users"] = [
            {
                "username": admin_name,
                "password": admin_pass,
                "admin": True,
                "enabled": True,
                "quota_bytes": quota,
            }
        ]
        _save(data)

    legacy_lib = core.CONFIG_DIR / "library"
    legacy_idx = core.CONFIG_DIR / "library.json"
    legacy_covers = core.CONFIG_DIR / "covers"
    legacy_reading = core.CONFIG_DIR / "reading.json"
    dest_root = user_paths.user_root(admin_name)
    dest_root.mkdir(parents=True, exist_ok=True)
    user_paths.library_dir(admin_name).mkdir(parents=True, exist_ok=True)
    user_paths.covers_dir(admin_name).mkdir(parents=True, exist_ok=True)
    user_paths.derived_dir(admin_name).mkdir(parents=True, exist_ok=True)

    dest_idx = user_paths.library_index(admin_name)
    dest_reading = user_paths.reading_state(admin_name)

    def _index_has_items(path: Path) -> bool:
        if not path.is_file():
            return False
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        return bool(data.get("items"))

    if legacy_idx.is_file() and not _index_has_items(dest_idx):
        if dest_idx.is_file():
            dest_idx.unlink()
        shutil.move(str(legacy_idx), str(dest_idx))
    elif not dest_idx.is_file():
        dest_idx.write_text('{\n  "items": []\n}\n')

    if legacy_reading.is_file() and not dest_reading.is_file():
        shutil.move(str(legacy_reading), str(dest_reading))
    elif not dest_reading.is_file():
        dest_reading.write_text('{\n  "items": {}\n}\n')

    if legacy_lib.is_dir():
        dest_lib = user_paths.library_dir(admin_name)
        dest_lib.mkdir(parents=True, exist_ok=True)
        for entry in legacy_lib.iterdir():
            target = dest_lib / entry.name
            if not target.exists():
                shutil.move(str(entry), str(target))
        try:
            legacy_lib.rmdir()
        except OSError:
            pass

    if legacy_covers.is_dir():
        dest_cov = user_paths.covers_dir(admin_name)
        dest_cov.mkdir(parents=True, exist_ok=True)
        for entry in legacy_covers.iterdir():
            target = dest_cov / entry.name
            if not target.exists():
                shutil.move(str(entry), str(target))
        try:
            legacy_covers.rmdir()
        except OSError:
            pass

    derived = core.CONFIG_DIR / "derived"
    if derived.is_dir() and any(derived.iterdir()):
        dest_der = user_paths.derived_dir(admin_name)
        dest_der.mkdir(parents=True, exist_ok=True)
        for entry in derived.iterdir():
            target = dest_der / entry.name
            if not target.exists():
                shutil.move(str(entry), str(target))


def reload_accounts() -> None:
    global _cache, _cache_mtime
    _cache = None
    _cache_mtime = None
    migrate_legacy()
    _load_raw()


def list_users() -> list[dict]:
    migrate_legacy()
    return list(_load_raw().get("users") or [])


def normalize_kindle_email(raw: object) -> str | None:
    if raw is None:
        return None
    email = str(raw).strip().lower()
    if not email:
        return None
    if not re.match(r"^[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}$", email):
        raise ValueError("Kindle email must look like name@kindle.com")
    if not any(email.endswith(suffix) for suffix in _KINDLE_SUFFIXES):
        raise ValueError("Use your Send-to-Kindle address (@kindle.com or @free.kindle.com)")
    return email


def kindle_email_for(username: str) -> str | None:
    row = get_user(username)
    if not row:
        return None
    val = str(row.get("kindle_email") or "").strip()
    return val or None


def get_user(username: str) -> dict | None:
    name = str(username or "").strip()
    if not name:
        return None
    for row in list_users():
        if str(row.get("username") or "") == name:
            return row
    return None


def is_admin(username: str) -> bool:
    row = get_user(username)
    return bool(row and row.get("admin"))


def verify_password(username: str, password: str) -> bool:
    row = get_user(username)
    if not row or not row.get("enabled", True):
        return False
    return secrets.compare_digest(
        password.encode(), str(row.get("password") or "").encode()
    )


def quota_bytes(username: str) -> int:
    row = get_user(username)
    if not row:
        return DEFAULT_USER_QUOTA
    return int(row.get("quota_bytes") or DEFAULT_USER_QUOTA)


def public_row(row: dict, used_bytes: int = 0) -> dict:
    out = {
        "username": row.get("username"),
        "admin": bool(row.get("admin")),
        "enabled": bool(row.get("enabled", True)),
        "quota_bytes": int(row.get("quota_bytes") or DEFAULT_USER_QUOTA),
        "used_bytes": used_bytes,
    }
    over = row.get("soulseek_limits")
    if isinstance(over, dict):
        out["soulseek_limits"] = over
    return out


def create_user(
    username: str,
    password: str,
    *,
    quota_bytes: int | None = None,
    admin: bool = False,
) -> dict:
    from . import user_paths

    name = _safe_username(username)
    if not password:
        raise ValueError("password required")
    if get_user(name):
        raise ValueError("Username already exists")
    data = _load_raw()
    row = {
        "username": name,
        "password": password,
        "admin": bool(admin),
        "enabled": True,
        "quota_bytes": int(quota_bytes or DEFAULT_USER_QUOTA),
    }
    data["users"].append(row)
    _save(data)
    user_paths.ensure_user_dirs(name)
    return public_row(row, 0)


def _validate_username(name: str) -> str:
    return _safe_username(name)


def _sync_config_login(old_name: str, new_name: str, password: str | None) -> None:
    try:
        cfg = load_config()
    except OSError:
        return
    if str(cfg.get("username") or "").strip() != old_name:
        return
    cfg["username"] = new_name
    if password:
        cfg["password"] = password
    path = core.CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    core._config = None


def rename_user(old_name: str, new_name: str) -> None:
    from . import jobs
    from . import user_paths
    import shutil

    old = _validate_username(old_name)
    new = _validate_username(new_name)
    if old == new:
        return
    if get_user(new):
        raise ValueError("Username already exists")
    data = _load_raw()
    users = data.get("users") or []
    idx = next((i for i, u in enumerate(users) if str(u.get("username")) == old), None)
    if idx is None:
        raise KeyError(old)
    src = user_paths.user_root(old)
    dest = user_paths.user_root(new)
    if src.is_dir():
        if dest.exists():
            raise ValueError("Destination user data already exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dest))
    elif not dest.is_dir():
        user_paths.ensure_user_dirs(new)
    row = users[idx]
    row["username"] = new
    users[idx] = row
    data["users"] = users
    _save(data)
    jobs.rewrite_job_owner(old, new)
    _sync_config_login(old, new, None)


def update_user(username: str, fields: dict) -> dict:
    from . import quota

    name = str(username or "").strip()
    if "new_username" in fields:
        new_name = str(fields.get("new_username") or "").strip()
        if new_name and new_name != name:
            rename_user(name, new_name)
            new_password = str(fields.get("password") or "")
            if new_password:
                _sync_config_login(name, new_name, new_password)
            name = new_name
    data = _load_raw()
    users = data.get("users") or []
    idx = next((i for i, u in enumerate(users) if str(u.get("username")) == name), None)
    if idx is None:
        raise KeyError(name)
    row = users[idx]
    if "password" in fields:
        pw = str(fields.get("password") or "")
        if pw:
            row["password"] = pw
            _sync_config_login(name, name, pw)
    if "quota_bytes" in fields:
        q = int(fields["quota_bytes"])
        if q < 0:
            raise ValueError("quota_bytes must be >= 0")
        used = quota.library_usage_for(name)["used_bytes"]
        if q < used:
            raise ValueError(f"Quota cannot be below current usage ({used} bytes)")
        row["quota_bytes"] = q
    if "soulseek_limits" in fields:
        raw = fields.get("soulseek_limits")
        if raw is None:
            row.pop("soulseek_limits", None)
        elif isinstance(raw, dict):
            cleaned: dict[str, int] = {}
            for key in ("searches_per_hour", "downloads_per_day", "concurrent_downloads"):
                if key in raw:
                    cleaned[key] = max(0, int(raw[key]))
            if cleaned:
                row["soulseek_limits"] = cleaned
            else:
                row.pop("soulseek_limits", None)
        else:
            raise ValueError("soulseek_limits must be an object")
    if "enabled" in fields:
        want_en = bool(fields["enabled"])
        if row.get("admin") and not want_en:
            others = [
                u
                for u in users
                if u.get("admin") and u.get("enabled", True) and str(u.get("username")) != name
            ]
            if not others:
                raise ValueError("Cannot disable the last admin")
        row["enabled"] = want_en
    if "admin" in fields:
        want = bool(fields["admin"])
        if row.get("admin") and not want:
            others = [u for u in users if u.get("admin") and str(u.get("username")) != name]
            if not others:
                raise ValueError("Cannot remove the last admin")
        row["admin"] = want
    if "kindle_email" in fields:
        raw = fields.get("kindle_email")
        if raw is None or str(raw).strip() == "":
            row.pop("kindle_email", None)
        else:
            row["kindle_email"] = normalize_kindle_email(raw)
    users[idx] = row
    data["users"] = users
    _save(data)
    return public_row(row, quota.library_usage_for(name)["used_bytes"])


def change_own_login(
    username: str,
    *,
    current_password: str,
    new_username: str | None = None,
    new_password: str | None = None,
    kindle_email: object = ...,
) -> str:
    """Verify current password; apply profile changes. Returns final username."""
    name = str(username or "").strip()
    if not verify_password(name, str(current_password or "")):
        raise PermissionError("Current password is incorrect")
    new_name = str(new_username or "").strip() if new_username else ""
    new_pw = str(new_password or "") if new_password else ""
    has_kindle = kindle_email is not ...
    if not new_name and not new_pw and not has_kindle:
        raise ValueError("Provide a change to save")
    fields: dict = {}
    if new_pw:
        fields["password"] = new_pw
    if new_name and new_name != name:
        fields["new_username"] = new_name
    if has_kindle:
        if kindle_email is None or str(kindle_email).strip() == "":
            fields["kindle_email"] = None
        else:
            fields["kindle_email"] = normalize_kindle_email(kindle_email)
    update_user(name, fields)
    return new_name if new_name and new_name != name else name


def delete_user(username: str) -> None:
    name = str(username or "").strip()
    data = _load_raw()
    users = data.get("users") or []
    row = get_user(name)
    if not row:
        raise KeyError(name)
    if row.get("admin"):
        admins = [u for u in users if u.get("admin") and u.get("enabled", True)]
        if len(admins) <= 1:
            raise ValueError("Cannot delete the last admin")
    data["users"] = [u for u in users if str(u.get("username")) != name]
    _save(data)