"""IRC feed and chat."""

from __future__ import annotations

from .. import irc_feed, irc_targets
from ..irc_worker import worker
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, qs: dict) -> bool:
    owner = handler._current_user
    if path == "/api/irc/feed":
        try:
            after = int((qs.get("after") or ["0"])[0])
        except (ValueError, TypeError, IndexError):
            after = 0
        handler.send_json(200, irc_feed.snapshot(after=after, viewer=owner))
        return True
    if path == "/api/irc/targets":
        handler.send_json(200, {"targets": irc_targets.list_targets()})
        return True
    return False


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/irc/chat":
        message = str(body.get("message") or "")
        channel = handler._validated_irc_channel(body.get("channel"))
        worker.send_chat(handler._current_user, channel, message)
        handler.send_json(200, {"ok": True})
        return True
    if path == "/api/irc/disconnect":
        was = worker.disconnect_now(owner=handler._current_user)
        handler.send_json(200, {"ok": True, "was_connected": was})
        return True
    return False