"""Pack chat attachment validation and per-viewer enrichment."""

from __future__ import annotations

from typing import Any

from . import library
from . import library_shares
from . import user_paths


MAX_ATTACHMENTS = 3
BOOK_INTENTS = frozenset({"recommend", "offer_copy"})


def _grant_public(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "grant_id": int(row["id"]),
        "owner": row["owner"],
        "requester": row["requester"],
        "status": row.get("status"),
        "mode_suggested": row.get("mode") if row.get("status") == "pending" else None,
        "mode": row.get("mode") if row.get("status") == "active" else None,
        "initiated_by": row.get("initiated_by") or "requester",
    }


def build_kennel_invite_attachment(owner: str, requester: str, mode_suggested: str | None) -> dict[str, Any]:
    grant = library_shares.create_owner_invite(owner, requester, mode_suggested)
    att = {"type": "kennel_invite", **_grant_public(grant)}
    return att


def build_library_book_attachment(owner: str, item_id: str, intent: str) -> dict[str, Any]:
    intent_s = str(intent or "recommend").strip().lower()
    if intent_s not in BOOK_INTENTS:
        raise ValueError("intent must be recommend or offer_copy")
    prev = user_paths.current_user_optional()
    user_paths.set_user(owner)
    try:
        row = library.get_item_row(item_id)
        if not library.is_registered(row):
            raise ValueError("Only catalogued books can be attached")
        return {
            "type": "library_book",
            "item_id": item_id,
            "owner": owner,
            "title": str(row.get("title") or ""),
            "authors": str(row.get("authors") or ""),
            "has_cover": bool(row.get("has_cover")),
            "intent": intent_s,
        }
    finally:
        user_paths.set_user(prev)


def validate_attachments_raw(
    sender: str,
    attachments: list,
    *,
    dm_peer: str | None,
) -> list[dict[str, Any]]:
    if not attachments:
        return []
    if len(attachments) > MAX_ATTACHMENTS:
        raise ValueError(f"At most {MAX_ATTACHMENTS} attachments")
    out: list[dict[str, Any]] = []
    for raw in attachments:
        if not isinstance(raw, dict):
            raise ValueError("Invalid attachment")
        typ = str(raw.get("type") or "").strip().lower()
        if typ == "kennel_invite":
            requester = str(raw.get("requester") or dm_peer or "").strip()
            if not requester:
                raise ValueError("requester required for kennel invite")
            mode = raw.get("mode_suggested") or raw.get("mode")
            mode_s = str(mode).strip() if mode is not None and str(mode).strip() else None
            out.append(build_kennel_invite_attachment(sender, requester, mode_s))
        elif typ == "library_book":
            item_id = str(raw.get("item_id") or "").strip()
            if not item_id:
                raise ValueError("item_id required")
            intent = str(raw.get("intent") or "recommend").strip().lower()
            out.append(build_library_book_attachment(sender, item_id, intent))
        else:
            raise ValueError("Unknown attachment type")
    return out


def enrich_attachment(att: dict[str, Any], viewer: str) -> dict[str, Any]:
    who = str(viewer or "").strip()
    out = dict(att)
    actions: dict[str, bool] = {}
    typ = str(att.get("type") or "")
    if typ == "kennel_invite":
        gid = int(att.get("grant_id") or 0)
        try:
            grant = library_shares.get_grant(gid)
            out.update(_grant_public(grant))
        except KeyError:
            out["status"] = "gone"
            grant = None
        if grant and grant.get("initiated_by") == "owner" and grant.get("status") == "pending":
            actions["can_accept_invite"] = who == grant.get("requester")
            actions["can_decline_invite"] = who == grant.get("requester")
        if grant and grant.get("status") == "active" and who == grant.get("requester"):
            actions["can_browse"] = True
        if grant and who == grant.get("owner"):
            actions["can_revoke"] = grant.get("status") == "active"
    elif typ == "library_book":
        item_id = str(att.get("item_id") or "")
        owner = str(att.get("owner") or "")
        item_gone = True
        if item_id and owner:
            try:
                prev = user_paths.current_user_optional()
                user_paths.set_user(owner)
                try:
                    library.get_item_row(item_id)
                    library.item_path(item_id)
                    item_gone = False
                except (KeyError, OSError):
                    item_gone = True
                finally:
                    user_paths.set_user(prev)
            except OSError:
                item_gone = True
        out["item_gone"] = item_gone
        intent = str(att.get("intent") or "recommend")
        claimed_by = att.get("claimed_by")
        if intent == "offer_copy" and claimed_by:
            out["claimed_by"] = str(claimed_by)
        can_read = False
        can_take = False
        if who and owner and not item_gone:
            if who == owner:
                can_read = True
            elif library_shares.can_read(who, owner):
                can_read = True
            if library_shares.can_take(who, owner):
                can_take = True
        actions["can_open_kennel"] = not item_gone
        actions["can_read"] = can_read and not item_gone
        actions["can_claim_copy"] = (
            intent == "offer_copy"
            and not item_gone
            and who
            and who != owner
            and not claimed_by
        )
        actions["can_take_shared"] = can_take and not item_gone and intent == "recommend"
        actions["can_ask"] = who and who != owner and not item_gone and intent == "recommend"
    out["actions"] = actions
    return out


def enrich_message(row: dict[str, Any], viewer: str, parent_cache: dict[int, dict]) -> dict[str, Any]:
    out = dict(row)
    atts = row.get("attachments")
    if isinstance(atts, list) and atts:
        out["attachments"] = [enrich_attachment(a, viewer) for a in atts if isinstance(a, dict)]
    pid = row.get("parent_id")
    if pid is not None:
        try:
            pid_i = int(pid)
        except (TypeError, ValueError):
            pid_i = 0
        if pid_i > 0:
            parent = parent_cache.get(pid_i)
            if parent:
                snippet = str(parent.get("text") or "")[:120]
                out["parent"] = {
                    "id": pid_i,
                    "username": parent.get("username"),
                    "text_snippet": snippet,
                }
    reactions = row.get("reactions")
    if isinstance(reactions, dict):
        out["reactions"] = {str(k): list(v) for k, v in reactions.items() if isinstance(v, list)}
    return out