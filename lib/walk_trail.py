"""Walk the Trail — tutorial fetch into Fresh catches (no live IRC)."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from . import jobs, library, user_paths
from .staging import create_staging

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "tutorial_minimal.mobi"
_QUERY_RE = re.compile(r"[^\w\s@+.,'\"()-]", re.UNICODE)
_MAX_QUERY_LEN = 120
_MAX_TITLE_LEN = 200


def _sanitize_query(query: str) -> str:
    raw = " ".join(str(query or "").split())
    if len(raw) < 2:
        raise ValueError("Query too short (min 2 characters)")
    if len(raw) > _MAX_QUERY_LEN:
        raw = raw[:_MAX_QUERY_LEN].rstrip()
    cleaned = _QUERY_RE.sub("", raw).strip()
    if len(cleaned) < 2:
        raise ValueError("Query has too few usable characters")
    return cleaned


def _fixture_fingerprint() -> str | None:
    from . import file_digest

    try:
        return file_digest.partial_md5(_FIXTURE).lower()
    except OSError:
        return None


def _find_staged_practice_item(display_title: str) -> dict | None:
    """Reuse an existing Fresh catch when the display title matches a prior tutorial fetch."""
    want = display_title.strip().lower()
    for row in library.list_items():
        if not library.is_staged(row):
            continue
        got = str(row.get("title") or "").strip().lower()
        if got == want:
            return row
        base = want.removesuffix(".mobi")
        if base and got == base + ".mobi":
            return row
    return None


def _find_existing_tutorial_item(display_title: str) -> dict | None:
    """Reuse any kennel row that is the same tutorial fixture (repeat tours, retitled practice)."""
    by_title = _find_staged_practice_item(display_title)
    if by_title:
        return by_title
    fp = _fixture_fingerprint()
    if not fp:
        return None
    for row in library.list_items():
        if str(row.get("partial_md5") or "").lower() == fp:
            return row
        fn = str(row.get("filename") or "").strip()
        if not fn:
            continue
        path = user_paths.library_dir() / fn
        try:
            from . import file_digest

            if file_digest.partial_md5(path).lower() == fp:
                return row
        except OSError:
            continue
    return None


def _title_from_query(query: str, title: str | None) -> str:
    hint = " ".join(str(title or "").split()).strip()
    if hint:
        if len(hint) > _MAX_TITLE_LEN:
            hint = hint[:_MAX_TITLE_LEN].rstrip()
        if not hint.lower().endswith(".mobi"):
            hint = hint + ".mobi" if "." not in Path(hint).name else hint
        return hint
    base = query.strip()
    if not base.lower().endswith(".mobi"):
        base = base + ".mobi"
    return base[:_MAX_TITLE_LEN]


def user_completed_trail(username: str) -> bool:
    from . import accounts

    return accounts.walk_trail_completed_at(username) is not None


def mark_trail_complete(username: str) -> dict:
    from . import accounts

    ts = accounts.mark_walk_trail_complete(username)
    return {"ok": True, "walk_trail_completed_at": ts}


def digest_walk_trail() -> dict:
    from . import accounts

    incomplete: list[str] = []
    completed = 0
    for row in accounts.list_users():
        if not row.get("enabled", True):
            continue
        u = str(row.get("username") or "").strip()
        if not u:
            continue
        if row.get("walk_trail_completed_at"):
            completed += 1
        else:
            incomplete.append(u)
    incomplete.sort()
    return {
        "completed_count": completed,
        "incomplete_usernames": incomplete,
    }


def complete_tutorial_fetch(owner: str, query: str, title: str | None = None) -> dict:
    """Stage tutorial MOBI and stash into Fresh catches for owner."""
    if not _FIXTURE.is_file():
        raise RuntimeError("Tutorial fixture missing")
    q = _sanitize_query(query)
    display_title = _title_from_query(q, title)
    user_paths.set_user(owner)
    job_id = jobs.new_id()
    staging_id = job_id
    base = create_staging(staging_id)
    raw = base / "raw.mobi"
    shutil.copy2(_FIXTURE, raw)
    size = raw.stat().st_size
    job: dict = {
        "id": job_id,
        "type": "download",
        "state": "done",
        "owner": owner,
        "staging_id": staging_id,
        "title": display_title,
        "raw_name": raw.name,
        "raw_bytes": size,
        "channel": "irchighway:ebooks",
        "walk_trail": True,
        "created_at": time.time(),
        "updated_at": time.time(),
    }
    jobs.save_job(job)
    item = library.auto_stash_from_job(job)
    if not item:
        item = _find_existing_tutorial_item(display_title)
    if not item:
        raise RuntimeError("Could not stash tutorial book")
    return {
        "ok": True,
        "job_id": job_id,
        "staging_id": staging_id,
        "library_item_id": item.get("id"),
        "title": item.get("title") or display_title,
        "item": item,
    }