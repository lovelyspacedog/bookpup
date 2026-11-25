"""OPDS catalog feeds."""

from __future__ import annotations

import base64
import mimetypes

from .. import accounts, kosync, library, opds as opds_mod, user_paths
from ..core import public_base_url
from . import auth_throttle
from ._types import RequestHandler


def opds_path(path: str) -> bool:
    return path == "/opds" or path.startswith("/opds/")


def opds_user(headers: dict[str, str], config: dict) -> str | None:
    user = kosync.auth_user(headers, config)
    if user:
        return user
    auth_hdr = headers.get("Authorization") or headers.get("authorization") or ""
    if not auth_hdr.startswith("Basic "):
        return None
    try:
        raw = base64.b64decode(auth_hdr[6:].strip(), validate=False).decode("utf-8")
        username, _, password = raw.partition(":")
        username = username.strip()
        if username and accounts.verify_password(username, password):
            return username
    except (ValueError, UnicodeDecodeError):
        return None
    return None


def route_opds_get(handler: RequestHandler, path: str) -> None:
    if auth_throttle.block_json(handler):
        return
    headers = handler._header_map()
    user = opds_user(headers, handler.config)
    auth_throttle.note_auth_result(handler, user)
    if not user:
        handler.send_response(401)
        handler.send_header("WWW-Authenticate", 'Basic realm="BookPup OPDS"')
        handler.send_header("Content-Type", "application/json")
        handler.end_headers()
        handler.wfile.write(b'{"error":"Authentication required"}')
        return
    accounts.migrate_legacy()
    user_paths.set_user(user)
    base = public_base_url(handler.config)
    if path == "/opds":
        body = opds_mod.feed_root(base)
    elif path == "/opds/catalog":
        body = opds_mod.feed_catalog(base, user)
    elif path.startswith("/opds/content/"):
        item_id = path[len("/opds/content/") :].strip("/")
        if not item_id or "/" in item_id:
            handler.send_json(400, {"error": "Invalid item id"})
            return
        row = library.get_item_row(item_id)
        if not library.is_registered(row):
            handler.send_json(403, {"error": "Catalogued bones only"})
            return
        file_path = library.item_path(item_id)
        ctype = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        handler.send_file(file_path, ctype, file_path.name)
        return
    else:
        handler.send_json(404, {"error": "Not found"})
        return
    handler.send_response(200)
    handler.send_header("Content-Type", "application/atom+xml;profile=opds-catalog")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-cache")
    handler.end_headers()
    handler.wfile.write(body)