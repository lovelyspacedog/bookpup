"""Soulseek search via slskd."""

from __future__ import annotations

from typing import Any

from . import irc_feed, jobs, slskd_client, user_paths
from .irc_targets import SOULSEEK_INDEX_ID
from .slskd_client import SlskdDisabledError, SlskdError
from .staging import create_staging

BOOK_EXT = frozenset(
    {".epub", ".mobi", ".azw3", ".pdf", ".cbz", ".cbr", ".cb7", ".djvu", ".fb2", ".chm", ".rtf"}
)


def _format_size(num_bytes: int | float | None) -> str | None:
    if num_bytes is None:
        return None
    try:
        n = float(num_bytes)
    except (TypeError, ValueError):
        return None
    if n < 0:
        return None
    units = ("B", "KB", "MB", "GB", "TB")
    u = 0
    while n >= 1024 and u < len(units) - 1:
        n /= 1024
        u += 1
    if u == 0:
        return f"{int(n)} {units[u]}"
    return f"{n:.1f} {units[u]}"


def _basename(path: str) -> str:
    p = path.replace("\\", "/").strip()
    if "/" in p:
        return p.rsplit("/", 1)[-1]
    return p


def _ext_of(filename: str) -> str:
    base = _basename(filename).lower()
    dot = base.rfind(".")
    if dot < 1:
        return ""
    return base[dot:]


def _map_file(item: dict[str, Any]) -> dict[str, Any]:
    username = str(item.get("username") or "").strip()
    filename = str(item.get("filename") or "").strip()
    search_id = str(item.get("search_id") or "").strip()
    try:
        size = int(item.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    title = _basename(filename)
    blob = {
        "username": username,
        "filename": filename,
        "size": size,
        "search_id": search_id,
    }
    return {
        "download_kind": "soulseek",
        "title": title,
        "size_hint": _format_size(size),
        "network": "Soulseek",
        "server": username or "—",
        "irc_target": SOULSEEK_INDEX_ID,
        "command": "soulseek",
        "soulseek": blob,
    }


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str, int]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        sk = row.get("soulseek")
        if not isinstance(sk, dict):
            continue
        key = (
            str(sk.get("username") or ""),
            str(sk.get("filename") or ""),
            int(sk.get("size") or 0),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _prefer_bookish(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bookish = [r for r in rows if _ext_of(str(r.get("title") or "")) in BOOK_EXT]
    if bookish:
        return bookish
    return rows


def search_remote(query: str) -> list[dict[str, Any]]:
    q = (query or "").strip()
    if not q:
        return []
    search_id = slskd_client.start_search(q)

    def _status(payload: dict[str, Any]) -> None:
        count = len(slskd_client._iter_response_files(payload))

    payload = slskd_client.wait_search_complete(search_id, on_tick=_status)
    files = slskd_client.flatten_search(payload, search_id=search_id)
    rows = [_map_file(f) for f in files]
    rows = _dedupe(rows)
    rows = _prefer_bookish(rows)
    return rows


def log_begin(query: str, *, owner: str | None = None) -> None:
    q = (query or "").strip()
    irc_feed.append_out("slskd", f'search "{q[:200]}"')
    irc_feed.append_session(f'Soulseek: sniffing for "{q[:120]}"…', owner=owner)


def log_done(query: str, count: int, *, owner: str | None = None) -> None:
    q = (query or "").strip()
    irc_feed.append_session(
        f'Soulseek: {count} match(es) for "{q[:80]}"',
        owner=owner,
    )


def log_failed(query: str, reason: str, *, owner: str | None = None) -> None:
    irc_feed.append_session(
        f'Soulseek failed ({query[:60]!r}): {reason[:160]}',
        owner=owner,
    )


def run_search_job(job: dict[str, Any], *, owner: str | None = None) -> None:
    job_id = str(job["id"])
    query = str(job.get("query") or "").strip()
    if owner:
        user_paths.set_user(owner)
    irc_feed.set_job_owner(owner)
    try:
        log_begin(query, owner=owner)
        job = jobs.load_job(job_id)
        job["state"] = "running"
        jobs.set_irc_status(job_id, "Querying Soulseek…")
        jobs.save_job(job)
        staging_id = job_id
        create_staging(staging_id)
        try:
            rows = search_remote(query)
        except SlskdDisabledError as exc:
            job = jobs.load_job(job_id)
            job["results"] = []
            job["result_count"] = 0
            job["staging_id"] = staging_id
            job["search_notice"] = str(exc)[:240]
            job["state"] = "done"
            job.pop("irc_status", None)
            log_done(query, 0, owner=owner)
            jobs.save_job(job)
            return
        except SlskdError as exc:
            log_failed(query, str(exc), owner=owner)
            job = jobs.load_job(job_id)
            job["state"] = "error"
            job["error"] = str(exc)[:400]
            job.pop("irc_status", None)
            jobs.save_job(job)
            return
        job = jobs.load_job(job_id)
        job["results"] = rows
        job["result_count"] = len(rows)
        job["staging_id"] = staging_id
        if not rows:
            job["search_notice"] = f'No Soulseek matches for "{query}"'
        job["state"] = "done"
        job.pop("error", None)
        job.pop("irc_status", None)
        jobs.save_job(job)
        log_done(query, len(rows), owner=owner)
        irc_feed.append_session(
            f"Sniff finished: {len(rows)} row(s) for {query!r}",
            owner=owner,
        )
    finally:
        irc_feed.set_job_owner(None)
        user_paths.set_user(None)