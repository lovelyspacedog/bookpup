"""Public sideload download by token; authenticated link creation lives in library routes."""

from __future__ import annotations

from .. import device_delivery, library, sideload_tokens, user_paths
from ._types import RequestHandler


def route_public_download_head(handler: RequestHandler, token: str) -> None:
    row = sideload_tokens.peek_token(token)
    if not row:
        handler.send_response(404)
        handler.send_header("Content-Length", "0")
        handler.end_headers()
        return
    owner = str(row.get("owner") or "")
    item_id = str(row.get("item_id") or "")
    delivery = str(row.get("delivery") or "source")
    user_paths.set_user(owner)
    try:
        item = library.get_item_row(item_id)
        if not library.is_registered(item):
            handler.send_response(403)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return
        path, mime, _filename = device_delivery.resolve_delivery(item_id, delivery)
        if not path.is_file():
            handler.send_response(404)
            handler.send_header("Content-Length", "0")
            handler.end_headers()
            return
        size = path.stat().st_size
        handler.send_response(200)
        handler.send_header("Content-Type", mime)
        handler.send_header("Content-Length", str(size))
        handler.send_header("Cache-Control", "no-cache")
        handler.end_headers()
    finally:
        user_paths.set_user(None)


def route_public_download(handler: RequestHandler, token: str) -> None:
    row = sideload_tokens.consume_token(token)
    if not row:
        handler.send_json(404, {"error": "Link expired or invalid"})
        return
    owner = str(row.get("owner") or "")
    item_id = str(row.get("item_id") or "")
    delivery = str(row.get("delivery") or "source")
    user_paths.set_user(owner)
    try:
        item = library.get_item_row(item_id)
        if not library.is_registered(item):
            handler.send_json(403, {"error": "Not a catalogued book"})
            return
        path, mime, filename = device_delivery.resolve_delivery(item_id, delivery)
        if not path.is_file():
            handler.send_json(404, {"error": "File missing"})
            return
        handler.send_bytes(path.read_bytes(), mime, filename)
    finally:
        user_paths.set_user(None)