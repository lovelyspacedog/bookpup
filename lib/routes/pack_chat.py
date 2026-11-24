"""Household pack chat API."""

from __future__ import annotations

from .. import pack_chat
from ._types import RequestHandler


def handle_get(handler: RequestHandler, path: str, qs: dict) -> bool:
    if path != "/api/pack/chat":
        return False
    try:
        after = int((qs.get("after") or ["0"])[0])
    except (ValueError, TypeError, IndexError):
        after = 0
    try:
        del_after = int((qs.get("del_after") or ["0"])[0])
    except (ValueError, TypeError, IndexError):
        del_after = 0
    data = pack_chat.snapshot(after, del_after, touch_user=handler._current_user)
    handler.send_json(200, data)
    return True


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/pack/chat":
        text = str(body.get("message") or "")

        def send() -> None:
            mid = pack_chat.append_message(handler._current_user, text)
            snap = pack_chat.snapshot(touch_user=handler._current_user)
            handler.send_json(
                200,
                {
                    "ok": True,
                    "id": mid,
                    "latest_id": snap["latest_id"],
                    "latest_del_seq": snap["latest_del_seq"],
                },
            )

        handler.dispatch(send)
        return True
    if path == "/api/pack/chat/clear":
        if not handler._is_admin:
            handler.send_json(403, {"error": "Admin access required"})
            return True

        def clear() -> None:
            pack_chat.clear_messages()
            snap = pack_chat.snapshot(touch_user=handler._current_user)
            handler.send_json(
                200,
                {
                    "ok": True,
                    "latest_id": snap["latest_id"],
                    "latest_del_seq": snap["latest_del_seq"],
                },
            )

        handler.dispatch(clear)
        return True
    return False


def handle_delete(handler: RequestHandler, path: str) -> bool:
    prefix = "/api/pack/chat/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :].strip()
    if not rest or "/" in rest:
        return False
    try:
        message_id = int(rest)
    except ValueError:
        handler.send_json(400, {"error": "Invalid message id"})
        return True

    def drop() -> None:
        pack_chat.delete_message(
            message_id,
            handler._current_user,
            is_admin=handler._is_admin,
        )
        snap = pack_chat.snapshot(touch_user=handler._current_user)
        handler.send_json(
            200,
            {
                "ok": True,
                "latest_id": snap["latest_id"],
                "latest_del_seq": snap["latest_del_seq"],
            },
        )

    handler.dispatch(drop)
    return True