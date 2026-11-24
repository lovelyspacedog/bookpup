"""KOReader sync protocol."""

from __future__ import annotations

from .. import accounts, kosync, user_paths
from ._types import RequestHandler


def kosync_path(path: str) -> bool:
    return path in ("/users/auth", "/users/create") or path.startswith("/syncs/progress")


def route_kosync_get(handler: RequestHandler, path: str) -> None:
    headers = handler._header_map()
    if path == "/users/auth":
        if kosync.auth_user(headers, handler.config):
            handler.send_ko_json(200, {"authorized": "OK"})
        else:
            code, body = kosync.unauthorized()
            handler.send_ko_json(code, body)
        return
    if path.startswith("/syncs/progress/"):
        user = kosync.auth_user(headers, handler.config)
        if not user:
            code, body = kosync.unauthorized()
            handler.send_ko_json(code, body)
            return
        accounts.migrate_legacy()
        user_paths.set_user(user)
        document = path[len("/syncs/progress/") :].strip("/")
        code, body = kosync.get_progress(document)
        handler.send_ko_json(code, body)
        return
    handler.send_ko_json(404, {"error": "Not found"})


def route_kosync_put(handler: RequestHandler, length: int) -> None:
    headers = handler._header_map()
    user = kosync.auth_user(headers, handler.config)
    if not user:
        code, body = kosync.unauthorized()
        handler.send_ko_json(code, body)
        return
    accounts.migrate_legacy()
    user_paths.set_user(user)
    if length > 65536:
        raise ValueError("Request too large")
    body = handler.read_json(length)
    code, data = kosync.put_progress(body)
    handler.send_ko_json(code, data)


def route_kosync_create(handler: RequestHandler, length: int) -> None:
    if length > 8192:
        raise ValueError("Request too large")
    body = handler.read_json(length)
    code, data = kosync.create_user(body, handler.config)
    handler.send_ko_json(code, data)