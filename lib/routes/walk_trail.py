"""Walk the Trail tutorial API."""

from __future__ import annotations

from .. import walk_trail
from ._types import RequestHandler


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path != "/api/walk-trail/fetch":
        return False
    query = str(body.get("query") or "").strip()
    title = body.get("title")
    if title is not None:
        title = str(title).strip() or None
    try:
        out = walk_trail.complete_tutorial_fetch(handler._current_user, query, title)
    except ValueError as exc:
        handler.send_json(400, {"error": str(exc)})
        return True
    except RuntimeError as exc:
        handler.send_json(500, {"error": str(exc)})
        return True
    handler.send_json(200, out)
    return True