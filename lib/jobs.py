"""Persistent job state on disk."""

from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path
from typing import Any

from . import core
from .core import DOWNLOAD_TIMEOUT, download_offer_timeout, ensure_dirs


def _jobs_dir() -> Path:
    return core.JOBS_DIR

RUNNING_STALE_SLACK = 90

_job_state_lock = threading.Lock()

JobDict = dict[str, Any]


def _path(job_id: str) -> Path:
    safe = job_id.replace("/", "_")
    return _jobs_dir() / f"{safe}.json"


def new_id() -> str:
    return secrets.token_urlsafe(12)


def create_job(job_type: str, **fields: Any) -> JobDict:
    ensure_dirs()
    job: JobDict = {
        "id": new_id(),
        "type": job_type,
        "state": "queued",
        "created_at": time.time(),
        "updated_at": time.time(),
        **fields,
    }
    save_job(job)
    return job


def rewrite_job_owner(old_owner: str, new_owner: str) -> int:
    old = str(old_owner or "").strip()
    new = str(new_owner or "").strip()
    if not old or not new or old == new:
        return 0
    count = 0
    for job in list_jobs():
        if str(job.get("owner") or "") == old:
            job["owner"] = new
            save_job(job)
            count += 1
    return count


def save_job(job: JobDict) -> None:
    ensure_dirs()
    job["updated_at"] = time.time()
    path = _path(str(job["id"]))
    data = json.dumps(job, indent=2) + "\n"
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data)
    tmp.replace(path)


def load_job(job_id: str) -> JobDict:
    path = _path(job_id)
    if not path.is_file():
        raise KeyError(job_id)
    last_exc: json.JSONDecodeError | None = None
    for attempt in range(5):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            last_exc = exc
            if attempt < 4:
                time.sleep(0.03)
                continue
            raise ValueError("Job record unreadable; retry in a moment") from exc
    raise ValueError("Job record unreadable") from last_exc


def assert_job_access(job_id: str, owner: str, admin: bool) -> JobDict:
    job = load_job(job_id)
    if not _owner_ok(job, owner, admin):
        raise PermissionError("Job not found")
    return job


def list_jobs() -> list[JobDict]:
    ensure_dirs()
    out: list[JobDict] = []
    for path in sorted(_jobs_dir().glob("*.json"), key=lambda p: p.stat().st_mtime):
        try:
            out.append(json.loads(path.read_text()))
        except json.JSONDecodeError:
            continue
    return out


def recover_interrupted_jobs() -> int:
    """On process start: running jobs are not in the worker queue anymore."""
    count = 0
    for job in list_jobs():
        if job.get("state") != "running":
            continue
        job["state"] = "error"
        job["error"] = "Interrupted (restart or timeout). Try again."
        save_job(job)
        fail_download_job(job, notify=False)
        count += 1
    return count


def _running_stale_limit(job: JobDict) -> float:
    if job.get("type") == "download":
        return download_offer_timeout() + DOWNLOAD_TIMEOUT + RUNNING_STALE_SLACK
    return DOWNLOAD_TIMEOUT + RUNNING_STALE_SLACK


def reconcile_stale_running() -> int:
    """Mark long-running jobs failed while the daemon is still up."""
    now = time.time()
    count = 0
    for job in list_jobs():
        if job.get("state") != "running":
            continue
        started = float(job.get("updated_at", job.get("created_at", now)))
        if now - started > _running_stale_limit(job):
            job["state"] = "error"
            job["error"] = "Timed out waiting for IRC/DCC. Try again or pick another server."
            save_job(job)
            fail_download_job(job, notify=False)
            count += 1
    return count


def job_summary(job: JobDict) -> JobDict:
    keys = (
        "id",
        "type",
        "state",
        "created_at",
        "updated_at",
        "channel",
        "query",
        "title",
        "command",
        "error",
        "parent_id",
        "result_count",
        "raw_bytes",
        "staging_id",
        "raw_name",
        "search_notice",
        "irc_status",
        "irc_status_at",
        "owner",
        "library_item_id",
    )
    return {k: job[k] for k in keys if k in job}


def _owner_ok(job: JobDict, owner: str, admin: bool) -> bool:
    if admin:
        return True
    return str(job.get("owner") or "") == owner


def set_irc_status(job_id: str, message: str) -> None:
    """Live status from IRC / worker while job is queued or running."""
    msg = " ".join(str(message or "").split())[:280]
    if not msg:
        return
    try:
        job = load_job(job_id)
    except KeyError:
        return
    if job.get("state") not in QUEUE_ACTIVE:
        return
    if job.get("irc_status") == msg:
        return
    job["irc_status"] = msg
    job["irc_status_at"] = time.time()
    save_job(job)


QUEUE_ACTIVE = ("queued", "running")
QUEUE_VISIBLE = ("queued", "running", "error", "cancelled")
DISMISSABLE = ("error", "cancelled")


def list_pending_jobs(*, owner: str | None = None, admin: bool = False) -> list[JobDict]:
    return list_queue_jobs(owner=owner, admin=admin)


def list_queue_jobs(*, owner: str | None = None, admin: bool = False) -> list[JobDict]:
    reconcile_stale_running()
    rows = [j for j in list_jobs() if j.get("state") in QUEUE_VISIBLE]
    if owner and not admin:
        rows = [j for j in rows if _owner_ok(j, owner, False)]

    def sort_key(job: JobDict) -> tuple:
        state = str(job.get("state"))
        rank = {"running": 0, "queued": 1, "error": 2, "cancelled": 3}.get(state, 9)
        return (rank, float(job.get("created_at", 0)))

    rows.sort(key=sort_key)
    return [job_summary(j) for j in rows]


def _norm_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def complete_search_no_matches(query: str, reason: str) -> list[str]:
    """Mark queued/running search jobs for this query as done with zero results."""
    qnorm = _norm_query(query)
    touched: list[str] = []
    for job in list_jobs():
        if job.get("type") != "search":
            continue
        if job.get("state") not in ("queued", "running"):
            continue
        if _norm_query(str(job.get("query", ""))) != qnorm:
            continue
        job["results"] = []
        job["result_count"] = 0
        job["staging_id"] = job["id"]
        job["search_notice"] = reason[:240]
        job["state"] = "done"
        job.pop("error", None)
        save_job(job)
        touched.append(str(job["id"]))
    return touched


def dismiss_job(job_id: str) -> None:
    job = load_job(job_id)
    if job.get("state") not in DISMISSABLE:
        raise ValueError("Only failed or cancelled jobs can be dismissed")
    _path(str(job["id"])).unlink(missing_ok=True)


def cancel_job(job_id: str) -> JobDict:
    with _job_state_lock:
        job = load_job(job_id)
        state = job.get("state")
        if state not in ("queued", "running"):
            raise ValueError("Only queued or running jobs can be cancelled")
        job["state"] = "cancelled"
        job.pop("error", None)
        job.pop("irc_status", None)
        job.pop("irc_status_at", None)
        save_job(job)
        return job_summary(job)


def fail_download_job(job: JobDict, *, notify: bool = True) -> None:
    """Mark download failed (if needed) and file admin fetch-fail inbox entry."""
    if str(job.get("type") or "") != "download":
        return
    if job.get("state") == "cancelled":
        return
    if notify and job.get("state") != "error":
        job = dict(job)
        job["state"] = "error"
        save_job(job)
    if str(job.get("state") or "") != "error":
        return
    from . import fetch_fail_inbox

    fetch_fail_inbox.record_failed_download(job)


def complete_job_success(job_id: str) -> JobDict | None:
    """Mark job done unless it was cancelled meanwhile. Returns job or None."""
    with _job_state_lock:
        job = load_job(job_id)
        state = job.get("state")
        if state in ("cancelled", "done"):
            return None
        job["state"] = "done"
        job.pop("error", None)
        job.pop("irc_status", None)
        job.pop("irc_status_at", None)
        save_job(job)
        return job


def queue_has_active_work() -> bool:
    """True when IRC may still be needed (queued or running jobs)."""
    for job in list_jobs():
        if job.get("state") in QUEUE_ACTIVE:
            return True
    return False


DONE_SEARCH_TTL = 900


def recent_done_search(*, owner: str | None, admin: bool = False) -> JobDict | None:
    """Latest finished sniff for this viewer (includes full results for table backfill)."""
    if not owner:
        return None
    now = time.time()
    best: JobDict | None = None
    best_at = 0.0
    for job in list_jobs():
        if job.get("type") != "search" or job.get("state") != "done":
            continue
        if not _owner_ok(job, owner, admin):
            continue
        results = job.get("results")
        if not isinstance(results, list) or not results:
            continue
        updated = float(job.get("updated_at") or 0)
        if now - updated > DONE_SEARCH_TTL:
            continue
        if updated > best_at:
            best_at = updated
            best = job
    if not best:
        return None
    slim = job_summary(best)
    slim["results"] = best.get("results")
    slim["result_count"] = best.get(
        "result_count", len(best.get("results") or [])
    )
    return slim


def recent_done_download(*, owner: str | None, admin: bool = False) -> JobDict | None:
    """Latest finished fetch for this viewer (toast / library refresh backfill)."""
    if not owner:
        return None
    now = time.time()
    best: JobDict | None = None
    best_at = 0.0
    for job in list_jobs():
        if job.get("type") != "download" or job.get("state") != "done":
            continue
        if not _owner_ok(job, owner, admin):
            continue
        if not int(job.get("raw_bytes") or 0):
            continue
        updated = float(job.get("updated_at") or 0)
        if now - updated > DONE_SEARCH_TTL:
            continue
        if updated > best_at:
            best_at = updated
            best = job
    if not best:
        return None
    return job_summary(best)


def queue_snapshot(*, owner: str | None = None, admin: bool = False) -> dict:
    jobs_list = list_queue_jobs(owner=owner, admin=admin)
    active = next((j for j in jobs_list if j.get("state") == "running"), None)
    if not active:
        active = next((j for j in jobs_list if j.get("state") == "queued"), None)
    pending = [j for j in jobs_list if j.get("state") in QUEUE_ACTIVE]
    return {
        "active": active,
        "queued": [j for j in pending if j is not active],
        "count": len(jobs_list),
        "jobs": jobs_list,
        "failed_count": sum(1 for j in jobs_list if j.get("state") in DISMISSABLE),
        "done_search": recent_done_search(owner=owner, admin=admin),
        "done_download": recent_done_download(owner=owner, admin=admin),
    }