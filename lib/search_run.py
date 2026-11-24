"""Start and wait for sniff jobs (shared by API and scheduled watches)."""

from __future__ import annotations

import time
from typing import Any

from . import irc_targets, jobs, soulseek_limits, soulseek_search, xdcc_search
from .core import SEARCH_TIMEOUT
from .irc_worker import worker
from .soulseek_limits import SoulseekLimitError
from .slskd_client import search_timeout_sec

JobsDict = dict[str, Any]


class SearchStartError(Exception):
    """Could not start a sniff (e.g. Soulseek cap)."""


def validate_search_channel(raw: object) -> str:
    cid = irc_targets.normalize_channel_id(str(raw or irc_targets.DEFAULT_SEARCH_TARGET))
    if cid in (
        irc_targets.SEARCH_ALL_ID,
        irc_targets.XDCC_INDEX_ID,
        irc_targets.SOULSEEK_INDEX_ID,
    ):
        return cid
    if irc_targets.is_xdcc_row_target(cid):
        return cid
    return irc_targets.resolve_target(cid).id


def search_wait_timeout(channel: str) -> float:
    cid = irc_targets.normalize_channel_id(channel)
    if irc_targets.is_soulseek_search(cid):
        return float(search_timeout_sec() + 45)
    if irc_targets.is_xdcc_search(cid):
        try:
            from .xdcc_search import _timeout

            return float(_timeout() + 45)
        except (TypeError, ValueError):
            return 90.0
    if irc_targets.is_search_all(cid):
        return float(SEARCH_TIMEOUT) * 3.0 + 150.0
    return float(SEARCH_TIMEOUT) + 90.0


def start_search(username: str, query: str, channel: str) -> JobsDict:
    q = str(query or "").strip()
    if not q:
        raise ValueError("query required")
    ch = validate_search_channel(channel)
    if ch == irc_targets.SOULSEEK_INDEX_ID:
        soulseek_limits.assert_search_allowed(username)
        soulseek_limits.record_search(username)
    job = jobs.create_job(
        "search",
        query=q,
        channel=ch,
        owner=username,
    )
    if ch == irc_targets.XDCC_INDEX_ID:
        xdcc_search.run_search_job(job, owner=username)
        return jobs.load_job(str(job["id"]))
    if ch == irc_targets.SOULSEEK_INDEX_ID:
        soulseek_search.run_search_job(job, owner=username)
        return jobs.load_job(str(job["id"]))
    worker.enqueue(job["id"])
    return job


def wait_for_search_job(job_id: str, channel: str, *, timeout: float | None = None) -> JobsDict:
    limit = timeout if timeout is not None else search_wait_timeout(channel)
    deadline = time.monotonic() + limit
    jid = str(job_id)
    while time.monotonic() < deadline:
        job = jobs.load_job(jid)
        state = str(job.get("state") or "")
        if state in ("done", "error", "cancelled"):
            return job
        time.sleep(0.4)
    job = jobs.load_job(jid)
    if str(job.get("state") or "") not in ("done", "error", "cancelled"):
        job["state"] = "error"
        job["error"] = "Scheduled sniff timed out waiting for results."
        jobs.save_job(job)
    return job


def run_search_job_for_user(
    username: str,
    query: str,
    channel: str,
    *,
    wait: bool = True,
    timeout: float | None = None,
) -> JobsDict:
    try:
        job = start_search(username, query, channel)
    except SoulseekLimitError as exc:
        raise SearchStartError(str(exc)) from exc
    ch = validate_search_channel(channel)
    if not wait:
        return job
    if ch in (irc_targets.XDCC_INDEX_ID, irc_targets.SOULSEEK_INDEX_ID):
        return job
    return wait_for_search_job(str(job["id"]), ch, timeout=timeout)