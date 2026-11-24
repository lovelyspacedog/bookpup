"""Whole-kennel sharing API."""

from __future__ import annotations

from .. import library
from .. import library_shares
from .. import pack_chat
from .. import transfer
from ..shared_library import catalog_context
from ._types import RequestHandler


def _dm(to_user: str, text: str) -> None:
    try:
        pack_chat.append_system_dm(to_user, text, kind="library_share")
    except (OSError, ValueError, PermissionError):
        pass


def handle_get(handler: RequestHandler, path: str, _qs: dict) -> bool:
    if path == "/api/library/shares":
        data = library_shares.list_for_user(handler._current_user)
        handler.send_json(200, data)
        return True
    prefix = "/api/library/shares/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :].strip("/")
    if rest.endswith("/catalog"):
        owner = rest[: -len("/catalog")].strip("/")
        if not owner or "/" in owner:
            handler.send_json(400, {"error": "Invalid owner"})
            return True
        if not library_shares.can_read(handler._current_user, owner):
            handler.send_json(403, {"error": "Shared kennel access denied"})
            return True
        with catalog_context(handler._current_user, owner):
            payload = library.status()
        payload["shared"] = True
        payload["owner"] = owner
        grant = library_shares.active_grant(handler._current_user, owner)
        payload["share_mode"] = grant.get("mode") if grant else None
        handler.send_json(200, payload)
        return True
    return False


def handle_post(handler: RequestHandler, path: str, body: dict) -> bool:
    if path == "/api/library/shares/invite":
        to_user = str(body.get("to") or "").strip()
        if not to_user:
            raise ValueError("to required")
        mode = body.get("mode")
        mode_s = str(mode).strip() if mode is not None and str(mode).strip() else None
        row = library_shares.create_owner_invite(handler._current_user, to_user, mode_s)
        _dm(
            to_user,
            f"{handler._current_user} invited you to browse their kennel — check Pack chat or Kennel → Sharing.",
        )
        handler.send_json(201, {"ok": True, "grant": row})
        return True
    if path.startswith("/api/library/shares/") and path.endswith("/accept-invite"):
        grant_id = _grant_action_id(path, "/accept-invite")
        mode = str(body.get("mode") or "").strip() or None
        row = library_shares.accept_invite_as_requester(grant_id, handler._current_user, mode)
        _dm(
            row["owner"],
            f"{handler._current_user} accepted your kennel invite ({row.get('mode')}).",
        )
        handler.send_json(200, {"ok": True, "grant": row})
        return True
    if path.startswith("/api/library/shares/") and path.endswith("/decline-invite"):
        grant_id = _grant_action_id(path, "/decline-invite")
        row = library_shares.decline_invite_as_requester(grant_id, handler._current_user)
        _dm(
            row["owner"],
            f"{handler._current_user} declined your kennel invite.",
        )
        handler.send_json(200, {"ok": True, "grant": row})
        return True
    if path == "/api/library/shares/request":
        owner = str(body.get("owner") or "").strip()
        if not owner:
            raise ValueError("owner required")
        row = library_shares.create_request(handler._current_user, owner)
        req = row["requester"]
        _dm(
            owner,
            f"{req} asked to browse your kennel — open Kennel → Sharing to accept or decline.",
        )
        handler.send_json(201, {"ok": True, "grant": row})
        return True
    prefix = "/api/library/shares/"
    if path.startswith(prefix) and path.endswith("/take"):
        # /api/library/shares/{owner}/items/{item_id}/take
        mid = path[len(prefix) : -len("/take")].strip("/")
        parts = [p for p in mid.split("/") if p]
        if len(parts) != 3 or parts[1] != "items":
            handler.send_json(404, {"error": "Not found"})
            return True
        owner, _items, item_id = parts[0], parts[1], parts[2]
        if not library_shares.can_take(handler._current_user, owner):
            raise PermissionError("Give access required to add to your kennel")
        item = transfer.send_library_item(owner, handler._current_user, item_id)
        handler.send_json(
            200,
            {
                "ok": True,
                "from": owner,
                "item": item,
            },
        )
        return True
    if path.startswith("/api/library/shares/") and path.endswith("/accept"):
        grant_id = _grant_action_id(path, "/accept")
        mode = str(body.get("mode") or "").strip()
        row = library_shares.accept_grant(grant_id, handler._current_user, mode)
        mode_label = "lend" if row.get("mode") == "lend" else "give"
        _dm(
            row["requester"],
            f'{handler._current_user} shared their kennel ({mode_label}) — open Kennel and pick their name in "Browsing".',
        )
        handler.send_json(200, {"ok": True, "grant": row})
        return True
    if path.startswith("/api/library/shares/") and path.endswith("/decline"):
        grant_id = _grant_action_id(path, "/decline")
        row = library_shares.decline_grant(grant_id, handler._current_user)
        _dm(
            row["requester"],
            f"{handler._current_user} declined your kennel browse request.",
        )
        handler.send_json(200, {"ok": True, "grant": row})
        return True
    if path.startswith("/api/library/shares/") and path.endswith("/revoke"):
        grant_id = _grant_action_id(path, "/revoke")
        row = library_shares.revoke_grant(
            grant_id, handler._current_user, is_admin=handler._is_admin
        )
        _dm(
            row["requester"],
            f"{handler._current_user} stopped sharing their kennel with you.",
        )
        handler.send_json(200, {"ok": True, "grant": row})
        return True
    return False


def _grant_action_id(path: str, suffix: str) -> int:
    base = path[: -len(suffix)]
    tail = base.rsplit("/", 1)[-1]
    try:
        return int(tail)
    except ValueError as exc:
        raise ValueError("Invalid share id") from exc


def handle_delete(handler: RequestHandler, path: str, qs: dict | None = None) -> bool:
    prefix = "/api/library/shares/"
    if not path.startswith(prefix):
        return False
    rest = path[len(prefix) :].strip("/")
    try:
        grant_id = int(rest)
    except ValueError:
        return False

    def cancel() -> None:
        row = library_shares.cancel_request(grant_id, handler._current_user)
        handler.send_json(200, {"ok": True, "grant": row})

    handler.dispatch(cancel)
    return True