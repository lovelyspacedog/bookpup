"""Search workspace and saved searches."""

from __future__ import annotations

from .. import irc_targets, jobs, search_workspace, soulseek_limits, soulseek_search, xdcc_search
from ..irc_worker import worker
from ..soulseek_limits import SoulseekLimitError
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    if path == "/api/search/workspace":
        handler.send_json(200, search_workspace.get_workspace())
        return True
    return False


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/search/workspace/draft":
        draft = search_workspace.update_draft(body)
        handler.send_json(200, {"ok": True, "draft": draft})
        return True
    if path == "/api/search/saved":
        out = search_workspace.save_draft_as(str(body.get("name") or ""))
        handler.send_json(201, out)
        return True
    if path.startswith("/api/search/saved/") and path.endswith("/load"):
        saved_id = path[len("/api/search/saved/") : -len("/load")]
        if not saved_id or "/" in saved_id:
            raise ValueError("Invalid saved id")
        try:
            draft = search_workspace.load_saved(saved_id)
        except KeyError:
            handler.send_json(404, {"error": "Saved search not found"})
            return True
        handler.send_json(200, {"ok": True, "draft": draft})
        return True
    if path == "/api/search/saved/reorder":
        ws = search_workspace.reorder_saved(body.get("order") or [])
        handler.send_json(200, {"ok": True, "workspace": ws})
        return True
    if path == "/api/search":
        query = str(body.get("query") or "").strip()
        if not query:
            raise ValueError("query required")
        channel = handler._validated_irc_channel(body.get("channel"))
        if channel == irc_targets.SOULSEEK_INDEX_ID:
            try:
                soulseek_limits.assert_search_allowed(handler._current_user)
            except SoulseekLimitError as exc:
                payload = {"error": str(exc)}
                if exc.limits:
                    payload["soulseek_limits"] = exc.limits
                handler.send_json(429, payload)
                return True
            soulseek_limits.record_search(handler._current_user)
        job = jobs.create_job(
            "search",
            query=query,
            channel=channel,
            owner=handler._current_user,
        )
        if channel == irc_targets.XDCC_INDEX_ID:
            xdcc_search.run_search_job(job, owner=handler._current_user)
            full = jobs.load_job(str(job["id"]))
            payload = jobs.job_summary(full)
            if full.get("state") == "done":
                payload["results"] = full.get("results")
                payload["result_count"] = full.get("result_count", 0)
            handler.send_json(201, {"job": payload})
            return True
        if channel == irc_targets.SOULSEEK_INDEX_ID:
            soulseek_search.run_search_job(job, owner=handler._current_user)
            full = jobs.load_job(str(job["id"]))
            payload = jobs.job_summary(full)
            if full.get("state") == "done":
                payload["results"] = full.get("results")
                payload["result_count"] = full.get("result_count", 0)
            handler.send_json(201, {"job": payload})
            return True
        worker.enqueue(job["id"])
        handler.send_json(201, {"job": job})
        return True
    return False


def handle_delete(handler: RequestHandler, path: str) -> bool:
    if not path.startswith("/api/search/saved/"):
        return False
    saved_id = path[len("/api/search/saved/") :]
    if not saved_id or "/" in saved_id or saved_id in ("reorder",):
        handler.send_json(404, {"error": "Not found"})
        return True

    def drop_saved() -> None:
        try:
            ws = search_workspace.delete_saved(saved_id)
        except KeyError:
            handler.send_json(404, {"error": "Saved search not found"})
            return
        handler.send_json(200, {"ok": True, "workspace": ws})

    handler.dispatch(drop_saved)
    return True