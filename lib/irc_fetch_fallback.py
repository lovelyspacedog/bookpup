"""After a refused IRC book fetch, try other ebook @search networks."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from . import gutenberg_fetch
from . import irc_feed
from . import jobs
from .core import MAX_DCC_SEARCH_BYTES
from .irc_client import DccOffer, DownloadRequestError, IrcSession, SearchNoMatchesError
from .irc_commands import _title_key, _title_match_score, resolve_download_command
from .irc_session_target import SessionTarget
from .irc_targets import normalize_channel_id, resolve_target, search_target_ids
from .search_results import parse_results_zip
from .staging import create_staging
from .title_match import titles_likely_same

if TYPE_CHECKING:
    from .irc_worker import IrcWorker

_MIN_ROW_SCORE = 60
_EXT_RE = re.compile(r"\.[a-z0-9]{2,5}$", re.IGNORECASE)


def alternate_irc_targets(failed_target_id: str) -> tuple[str, ...]:
    cur = normalize_channel_id(failed_target_id)
    return tuple(t for t in search_target_ids() if normalize_channel_id(t) != cur)


def _session_target(target_id: str) -> SessionTarget:
    t = resolve_target(target_id)
    return SessionTarget(
        id=t.id,
        network=t.network,
        channel=t.channel,
        server=t.server,
        port=t.port,
        use_tls=t.use_tls,
    )


def fallback_search_query(job: dict, parent: dict | None) -> str:
    if parent:
        q = str(parent.get("query") or "").strip()
        if q:
            return q
    title = str(job.get("title") or "").strip()
    if not title:
        cmd = str(job.get("command_original") or job.get("command") or "")
        title = re.sub(r"^![^\s]+\s+", "", cmd).strip()
    if _EXT_RE.search(title):
        title = _EXT_RE.sub("", title).strip()
    return title or "ebook"


def _row_match_score(row: dict, title: str, command: str) -> int:
    keys = {_title_key(command), _title_key(title)}
    keys.discard("")
    if not keys:
        return 0
    cmd = str(row.get("command") or "")
    tkey = _title_key(str(row.get("title") or cmd))
    if not tkey:
        return 0
    score = max(_title_match_score(k, tkey) for k in keys)
    if cmd.lower().startswith("!get "):
        score += 40
    row_title = str(row.get("title") or "")
    if titles_likely_same(title, row_title) or titles_likely_same(command, row_title):
        score += 25
    return score


def pick_best_row(
    rows: list[dict],
    *,
    title: str,
    command: str,
) -> dict | None:
    best: dict | None = None
    best_score = 0
    for row in rows:
        score = _row_match_score(row, title, command)
        if score > best_score and score >= _MIN_ROW_SCORE:
            best_score = score
            best = row
    return best


def _request_with_gutenberg(
    session: IrcSession,
    channel: str,
    irc_cmd: str,
    dest: Path,
    max_bytes: int,
    title: str | None,
    on_status: Callable[[str], None] | None,
) -> DccOffer:
    try:
        return session.request_book(channel, irc_cmd, str(dest), max_bytes=max_bytes)
    except DownloadRequestError as exc:
        fb = gutenberg_fetch.gutenberg_fallback_after_irc_refusal(
            reason=str(exc),
            command=irc_cmd,
            title=title,
            dest_path=dest,
            on_status=on_status,
        )
        if fb is None:
            raise
        irc_feed.append_session(fb.feed)
        return fb.offer


def _attempt_on_target(
    worker: IrcWorker,
    *,
    job_id: str,
    job: dict,
    target_id: str,
    irc_cmd: str,
    title: str | None,
    dest: Path,
    max_bytes: int,
    search_results: list[dict] | None,
    all_results: list[dict] | None,
    owner: str | None,
) -> DccOffer:
    st = _session_target(target_id)
    jobs.set_irc_status(job_id, f"Retry fetch on {st.display}…")
    irc_feed.append_session(f"Trying {st.display}: {irc_cmd[:120]}")
    session = worker._ensure_session(st, feed_owner=owner, job_id=job_id)
    worker._bind_session_status(job_id)
    resolved, hint, redirect = resolve_download_command(
        target_id,
        irc_cmd,
        title=title,
        search_results=search_results or [],
        all_search_results=all_results,
    )
    use_target = redirect or target_id
    if redirect and redirect != target_id:
        st = _session_target(use_target)
        jobs.set_irc_status(job_id, f"Redirecting to {st.display}…")
        session = worker._ensure_session(st, feed_owner=owner, job_id=job_id)
        worker._bind_session_status(job_id)
    if hint:
        irc_feed.append_session(str(hint))
    channel = st.channel

    def on_status(msg: str) -> None:
        jobs.set_irc_status(job_id, msg)

    offer = _request_with_gutenberg(
        session,
        channel,
        resolved,
        dest,
        max_bytes,
        title,
        on_status,
    )
    job = jobs.load_job(job_id)
    if not job.get("fetch_fallback_from"):
        job["fetch_fallback_from"] = normalize_channel_id(str(job.get("channel") or ""))
    job["channel"] = use_target
    job["command"] = resolved
    if irc_cmd != resolved:
        job["command_original"] = job.get("command_original") or irc_cmd
    attempts = job.get("fetch_fallback_attempts")
    if not isinstance(attempts, list):
        attempts = []
    attempts.append({"target": use_target, "command": resolved, "ok": True})
    job["fetch_fallback_attempts"] = attempts
    jobs.save_job(job)
    return offer


def _parent_pool(job: dict) -> tuple[dict | None, list[dict]]:
    parent_id = str(job.get("parent_id") or "").strip()
    if not parent_id:
        return None, []
    try:
        parent = jobs.load_job(parent_id)
    except KeyError:
        return None, []
    if parent.get("type") != "search":
        return None, []
    raw = parent.get("results")
    return parent, list(raw) if isinstance(raw, list) else []


def _parent_rows_by_target(
    all_rows: list[dict],
    failed_tid: str,
    title: str,
    command: str,
) -> dict[str, dict]:
    failed = normalize_channel_id(failed_tid)
    out: dict[str, dict] = {}
    for row in all_rows:
        tid = normalize_channel_id(str(row.get("irc_target") or ""))
        if not tid or tid == failed or tid not in search_target_ids():
            continue
        score = _row_match_score(row, title, command)
        if score < _MIN_ROW_SCORE:
            continue
        prev = out.get(tid)
        if prev is None or score > _row_match_score(prev, title, command):
            out[tid] = row
    return out


def try_other_irc_networks(
    worker: IrcWorker,
    *,
    job_id: str,
    job: dict,
    failed_target_id: str,
    dest: Path,
    max_bytes: int,
    title: str,
    command: str,
    first_reason: str,
) -> DccOffer:
    """Connect, @search if needed, and fetch on other IRC ebook channels."""
    owner = str(job.get("owner") or "").strip() or None
    failed_tid = normalize_channel_id(failed_target_id)
    original_cmd = str(job.get("command_original") or command).strip()
    failures: list[str] = [f"{failed_tid}: {first_reason[:120]}"]

    parent, all_rows = _parent_pool(job)

    for tid in search_target_ids():
        if normalize_channel_id(tid) == failed_tid:
            continue
        row = _parent_rows_by_target(all_rows, failed_tid, title, original_cmd).get(tid)
        if not row:
            continue
        row_cmd = str(row.get("command") or "").strip()
        if not row_cmd.startswith("!"):
            continue
        try:
            return _attempt_on_target(
                worker,
                job_id=job_id,
                job=job,
                target_id=tid,
                irc_cmd=row_cmd,
                title=str(row.get("title") or title) or None,
                dest=dest,
                max_bytes=max_bytes,
                search_results=[r for r in all_rows if normalize_channel_id(str(r.get("irc_target") or "")) == tid],
                all_results=all_rows,
                owner=owner,
            )
        except DownloadRequestError as exc:
            failures.append(f"{tid} (cached row): {exc}")
            worker._reset_session()
        except Exception as exc:
            failures.append(f"{tid} (cached row): {exc}")
            worker._reset_session()

    query = fallback_search_query(job, parent)
    staging_id = str(job.get("staging_id") or job_id)
    staging_dir = create_staging(staging_id)
    tried_search: set[str] = set()

    for tid in alternate_irc_targets(failed_tid):
        if tid in tried_search:
            continue
        tried_search.add(tid)
        st = _session_target(tid)
        jobs.set_irc_status(job_id, f"Sniff {st.network} for fallback…")
        irc_feed.append_session(f"Fetch refused — @search on {st.display} ({query[:80]!r})")
        zip_path = staging_dir / f"fallback-{normalize_channel_id(tid).replace(':', '-')}.zip"
        try:
            session = worker._ensure_session(st, feed_owner=owner, job_id=job_id)
            worker._bind_session_status(job_id)
            session.search_and_download_results(
                st.channel,
                query,
                str(zip_path),
                max_bytes=MAX_DCC_SEARCH_BYTES,
            )
            rows = [r.to_dict() for r in parse_results_zip(str(zip_path))]
            for entry in rows:
                entry.setdefault("irc_target", tid)
                entry.setdefault("network", st.network)
        except SearchNoMatchesError as exc:
            failures.append(f"{tid}: no matches ({exc})")
            worker._reset_session()
            continue
        except Exception as exc:
            failures.append(f"{tid}: search failed ({exc})")
            worker._reset_session()
            continue

        pick = pick_best_row(rows, title=title, command=original_cmd)
        if pick is None:
            failures.append(f"{tid}: no row similar to {title[:60]!r}")
            worker._reset_session()
            continue
        row_cmd = str(pick.get("command") or "").strip()
        try:
            return _attempt_on_target(
                worker,
                job_id=job_id,
                job=job,
                target_id=tid,
                irc_cmd=row_cmd,
                title=str(pick.get("title") or title) or None,
                dest=dest,
                max_bytes=max_bytes,
                search_results=rows,
                all_results=all_rows or None,
                owner=owner,
            )
        except DownloadRequestError as exc:
            failures.append(f"{tid}: {exc}")
            worker._reset_session()
        except Exception as exc:
            failures.append(f"{exc}")
            worker._reset_session()

    summary = "; ".join(failures)[:380]
    job = jobs.load_job(job_id)
    job["fetch_fallback_attempts"] = failures
    jobs.save_job(job)
    raise DownloadRequestError(
        f"No IRC network returned this book ({len(failures)} attempt(s)). {summary}"
    )