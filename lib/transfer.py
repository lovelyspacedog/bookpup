"""Send library items and staged downloads between household accounts."""

from __future__ import annotations

from . import accounts
from . import covers
from . import jobs
from . import library
from . import quota
from . import user_paths
from .staging import staging_dir


def household_usernames() -> list[str]:
    names = [
        str(u.get("username") or "").strip()
        for u in accounts.list_users()
        if u.get("enabled", True)
    ]
    return sorted(n for n in names if n)


def _validate_recipient(from_user: str, to_user: str) -> None:
    sender = str(from_user or "").strip()
    dest = str(to_user or "").strip()
    if not dest:
        raise ValueError("Recipient required")
    if dest == sender:
        raise ValueError("Cannot send to yourself")
    row = accounts.get_user(dest)
    if not row or not row.get("enabled", True):
        raise ValueError("Unknown user")


def _staging_owner(staging_id: str) -> str | None:
    try:
        job = jobs.load_job(staging_id)
        return str(job.get("owner") or "").strip() or None
    except KeyError:
        pass
    for job in jobs.list_jobs():
        sid = str(job.get("staging_id") or job.get("id") or "")
        if sid == staging_id:
            return str(job.get("owner") or "").strip() or None
    return None


def assert_staging_access(staging_id: str, owner: str, admin: bool) -> None:
    sid = str(staging_id or "").strip()
    if not staging_dir(sid).is_dir():
        raise KeyError(sid)
    job_owner = _staging_owner(sid)
    if job_owner:
        if job_owner != owner and not admin:
            raise PermissionError("Staging not found")
        return
    if admin:
        return
    raise PermissionError("Staging not found")


def send_library_item(from_user: str, to_user: str, item_id: str) -> dict:
    _validate_recipient(from_user, to_user)
    try:
        user_paths.set_user(from_user)
        row = library.get_item_row(item_id)
        path = library.item_path(item_id)
        data = path.read_bytes()
        cover_path = covers.resolve_cover_path(item_id)
        cover_data = cover_path.read_bytes() if cover_path and cover_path.is_file() else None
        extra = len(data) + len(cover_data or b"")
        quota.assert_can_store(extra, username=to_user)
        user_paths.set_user(to_user)
        return library.clone_item_copy(row, data, cover_data)
    finally:
        user_paths.set_user(from_user)


def send_staging(
    from_user: str,
    to_user: str,
    staging_id: str,
    *,
    title_hint: str | None = None,
    admin: bool = False,
) -> dict:
    _validate_recipient(from_user, to_user)
    assert_staging_access(staging_id, from_user, admin)
    base = staging_dir(staging_id)
    raw_candidates = sorted(base.glob("raw*"), key=lambda p: p.stat().st_size, reverse=True)
    if not raw_candidates:
        raise ValueError("No staged raw file")
    from .staging import extract_for_library

    _, size = extract_for_library(raw_candidates[0])
    quota.assert_can_store(size, username=to_user)
    try:
        user_paths.set_user(to_user)
        return library.save_from_staging(staging_id, title_hint)
    finally:
        user_paths.set_user(from_user)