"""Walk the Trail — tutorial fetch into Fresh catches (no live IRC)."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path

from . import jobs, library, user_paths
from .staging import create_staging

_FIXTURE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "tutorial_minimal.mobi"
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
        raise RuntimeError("Could not stash tutorial book")
    return {
        "ok": True,
        "job_id": job_id,
        "staging_id": staging_id,
        "library_item_id": item.get("id"),
        "title": item.get("title") or display_title,
        "item": item,
    }