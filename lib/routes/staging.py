"""Staging raw download and send."""

from __future__ import annotations

import mimetypes

from .. import transfer
from ..staging import staging_dir
from ._types import RequestHandler


def send_staging_raw(handler: RequestHandler, staging_id: str) -> None:
    transfer.assert_staging_access(
        staging_id, handler._current_user, handler._is_admin
    )
    base = staging_dir(staging_id)
    if not base.is_dir():
        raise KeyError(staging_id)
    raw_files = list(base.glob("raw*"))
    if not raw_files:
        raise ValueError("Nothing staged")
    raw = raw_files[0]
    ctype = mimetypes.guess_type(raw.name)[0] or "application/octet-stream"
    handler.send_bytes(raw.read_bytes(), ctype, raw.name)


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if not path.startswith("/api/staging/") or not path.endswith("/send"):
        return False
    staging_id = path[len("/api/staging/") : -len("/send")].strip("/")
    if not staging_id or "/" in staging_id:
        raise ValueError("Invalid staging id")
    to_user = str(body.get("to") or "").strip()
    title = str(body.get("title") or "").strip() or None
    item = transfer.send_staging(
        handler._current_user,
        to_user,
        staging_id,
        title_hint=title,
        admin=handler._is_admin,
    )
    handler.send_json(
        201,
        {
            "ok": True,
            "to": to_user,
            "item": item,
        },
    )
    return True