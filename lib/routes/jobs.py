"""Job queue and job actions."""

from __future__ import annotations

from .. import irc_feed, job_download, job_select, jobs
from ..irc_worker import worker
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    owner = handler._current_user
    admin = handler._is_admin
    if path == "/api/queue":
        snap = jobs.queue_snapshot(owner=owner, admin=admin)
        snap["irc"] = worker.health_snapshot()
        handler.send_json(200, snap)
        return True
    if path == "/api/jobs":
        handler.send_json(200, {"jobs": jobs.list_pending_jobs(owner=owner, admin=admin)})
        return True
    if path.startswith("/api/jobs/"):
        job_id = path[len("/api/jobs/") :]
        if not job_id or "/" in job_id:
            handler.send_json(400, {"error": "Invalid job id"})
            return True
        job = jobs.assert_job_access(job_id, owner, admin)
        slim = jobs.job_summary(job)
        if job.get("type") == "search" and job.get("results") is not None:
            if job.get("state") in ("done", "running"):
                slim["results"] = job.get("results")
                slim["result_count"] = job.get(
                    "result_count", len(job.get("results") or [])
                )
        handler.send_json(200, slim)
        return True
    return False


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path.startswith("/api/jobs/") and path.endswith("/select-batch"):
        search_id = path[len("/api/jobs/") : -len("/select-batch")]
        parent = jobs.assert_job_access(search_id, handler._current_user, handler._is_admin)
        rows_in = body.get("rows")
        if not isinstance(rows_in, list) or not rows_in:
            raise ValueError("rows required (array of search result objects)")
        cap = body.get("max")
        try:
            limit = int(cap) if cap is not None else 3
        except (TypeError, ValueError):
            limit = 3
        limit = max(1, min(limit, job_select.BATCH_MAX))
        if len(rows_in) > limit:
            raise ValueError(f"At most {limit} fetches per batch (server cap {job_select.BATCH_MAX})")
        created = []
        errors: list[str] = []
        for row in rows_in:
            if not isinstance(row, dict):
                continue
            try:
                validated = job_download.validate_fetch_row(row)
            except ValueError as exc:
                errors.append(str(exc)[:160])
                continue
            title = str(row.get("title") or "").strip() or None
            target = row.get("irc_target")
            try:
                job = job_select.create_download_from_search(
                    parent,
                    command=validated.command or "",
                    title=title,
                    irc_target=str(target) if target else None,
                    owner=handler._current_user,
                    validated_channel=handler._validated_irc_channel,
                    row=row,
                    xdcc=validated.xdcc,
                    soulseek=validated.soulseek,
                )
                created.append(jobs.job_summary(job))
            except (ValueError, PermissionError) as exc:
                errors.append(str(exc)[:160])
        handler.send_json(201, {"ok": True, "jobs": created, "errors": errors})
        return True
    if path.startswith("/api/jobs/") and path.endswith("/select"):
        search_id = path[len("/api/jobs/") : -len("/select")]
        parent = jobs.assert_job_access(search_id, handler._current_user, handler._is_admin)
        row_body = {
            "command": body.get("command"),
            "title": body.get("title"),
            "download_kind": body.get("download_kind"),
            "xdcc": body.get("xdcc"),
            "soulseek": body.get("soulseek"),
            "irc_target": body.get("irc_target"),
        }
        validated = job_download.validate_fetch_row(row_body)
        title = str(body.get("title") or "").strip() or None
        try:
            job = job_select.create_download_from_search(
                parent,
                command=validated.command or "",
                title=title,
                irc_target=body.get("irc_target"),
                owner=handler._current_user,
                validated_channel=handler._validated_irc_channel,
                row=row_body,
                xdcc=validated.xdcc,
                soulseek=validated.soulseek,
            )
        except PermissionError as exc:
            from ..soulseek_limits import SoulseekLimitError

            payload = {"error": str(exc)}
            if isinstance(exc, SoulseekLimitError) and exc.limits:
                payload["soulseek_limits"] = exc.limits
            handler.send_json(429, payload)
            return True
        handler.send_json(201, {"job": job})
        return True
    if path.startswith("/api/jobs/") and path.endswith("/cancel"):
        job_id = path[len("/api/jobs/") : -len("/cancel")]
        if not job_id:
            raise ValueError("Invalid job id")
        jobs.assert_job_access(job_id, handler._current_user, handler._is_admin)
        cancelled = jobs.cancel_job(job_id)
        worker.interrupt(job_id)
        if str(cancelled.get("type") or "") == "download":
            from .. import library

            sid = str(cancelled.get("staging_id") or cancelled.get("id") or "")
            library.discard_download_staging(sid)
        irc_feed.append_session(
            f"Job cancelled: {job_id} ({cancelled.get('type')})",
            owner=str(cancelled.get("owner") or "") or None,
        )
        handler.send_json(200, {"ok": True, "job": cancelled})
        return True
    if path.startswith("/api/jobs/") and path.endswith("/dismiss"):
        job_id = path[len("/api/jobs/") : -len("/dismiss")]
        if not job_id:
            raise ValueError("Invalid job id")
        jobs.assert_job_access(job_id, handler._current_user, handler._is_admin)
        jobs.dismiss_job(job_id)
        handler.send_json(200, {"ok": True})
        return True
    if path.startswith("/api/jobs/") and path.endswith("/retry"):
        job_id = path[len("/api/jobs/") : -len("/retry")]
        if not job_id:
            raise ValueError("Invalid job id")
        job = jobs.assert_job_access(job_id, handler._current_user, handler._is_admin)
        if job.get("type") != "download":
            raise ValueError("Only fetch jobs can be retried")
        if job.get("state") != "error":
            raise ValueError("Only failed jobs can be retried")
        parent_id = str(job.get("parent_id") or "").strip()
        if not parent_id:
            raise ValueError("This job has no parent search to retry from")
        parent = jobs.load_job(parent_id)
        if parent.get("type") != "search":
            raise ValueError("Parent job is not a search")
        command = str(job.get("command_original") or job.get("command") or "").strip()
        xdcc_blob = job.get("xdcc") if isinstance(job.get("xdcc"), dict) else None
        if not xdcc_blob and not command.startswith("!"):
            raise ValueError("Missing IRC command on failed job")
        title = str(job.get("title") or "").strip() or None
        irc_target = job.get("channel") if parent.get("channel") == "all" else job.get("fetch_redirect_target")
        new_job = job_select.create_download_from_search(
            parent,
            command=command,
            title=title,
            irc_target=str(irc_target) if irc_target else None,
            owner=handler._current_user,
            validated_channel=handler._validated_irc_channel,
            xdcc=xdcc_blob,
        )
        jobs.dismiss_job(job_id)
        handler.send_json(201, {"ok": True, "job": jobs.job_summary(new_job)})
        return True
    return False