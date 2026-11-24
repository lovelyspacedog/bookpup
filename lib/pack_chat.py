"""Household pack chat (persisted messages, in-memory presence)."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

from . import accounts
from . import core
from . import json_atomic
from . import transfer

PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
MAX_MESSAGES = 500
MAX_DELETIONS_LOG = 200
PRESENCE_TTL_SECONDS = 90
MESSAGE_MAX_LEN = 2000
ALLOWED_REACTIONS = frozenset({"paw", "heart", "laugh"})
SYSTEM_SENDER = "bookpup"
BUGBOT_SENDER = "bugbot"
FEATURECAT_SENDER = "featurecat"
VIRTUAL_PEERS = frozenset({SYSTEM_SENDER, BUGBOT_SENDER, FEATURECAT_SENDER})


def is_virtual_peer(name: str) -> bool:
    key = str(name or "").strip().lower()
    return key in {p.lower() for p in VIRTUAL_PEERS}


def is_virtual_sender(name: str) -> bool:
    return is_virtual_peer(name)

_CTRL_RE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")

_lock = threading.Lock()
_loaded = False
_messages: list[dict[str, Any]] = []
_next_id = 1
_deletions: list[dict[str, Any]] = []
_del_seq = 0
_presence: dict[str, float] = {}


def sanitize_message(text: str) -> str:
    text = _CTRL_RE.sub("", str(text or ""))
    return text.strip()


def _message_recipient(row: dict[str, Any]) -> str | None:
    dest = row.get("to")
    if dest is None:
        return None
    cleaned = str(dest).strip()
    return cleaned or None


def is_pack_message(row: dict[str, Any]) -> bool:
    return _message_recipient(row) is None


def visible_to(row: dict[str, Any], viewer: str, *, is_admin: bool = False) -> bool:
    who = str(viewer or "").strip()
    if not who:
        return False
    if is_pack_message(row):
        return True
    sender = str(row.get("username") or "").strip()
    dest = _message_recipient(row) or ""
    if who == sender or who == dest:
        return True
    return bool(is_admin)


def _canonical_virtual_peer(name: str) -> str | None:
    key = str(name or "").strip().lower()
    for peer in VIRTUAL_PEERS:
        if peer.lower() == key:
            return peer
    return None


def _validate_dm_recipient(from_user: str, to_user: str) -> str:
    dest = str(to_user).strip()
    canon = _canonical_virtual_peer(dest)
    if canon:
        if canon == SYSTEM_SENDER:
            raise ValueError("BookPup alerts are read-only")
        sender = str(from_user or "").strip()
        if not sender or sender.lower() == canon.lower():
            raise ValueError("Cannot send to yourself")
        row = accounts.get_user(sender)
        if not row or not row.get("enabled", True):
            raise ValueError("Unknown user")
        return canon
    transfer._validate_recipient(from_user, to_user)
    return dest


def _row_out(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    if _message_recipient(row) is None:
        out.pop("to", None)
    return out


def _trim_messages_unlocked() -> None:
    global _del_seq
    while len(_messages) > MAX_MESSAGES:
        dropped = _messages.pop(0)
        _del_seq += 1
        _deletions.append(
            {
                "del_seq": _del_seq,
                "message_id": int(dropped["id"]),
                "ts": time.time(),
            }
        )


def _load_unlocked() -> None:
    global _loaded, _messages, _next_id, _deletions, _del_seq
    path = PACK_CHAT_FILE
    _messages = []
    _next_id = 1
    _deletions = []
    _del_seq = 0
    if path.is_file():
        try:
            raw = json.loads(path.read_text())
            if isinstance(raw, dict):
                rows = raw.get("messages")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        mid = int(row.get("id") or 0)
                        user = str(row.get("username") or "").strip()
                        text = str(row.get("text") or "")
                        ts = float(row.get("ts") or 0)
                        atts = row.get("attachments")
                        has_atts = isinstance(atts, list) and len(atts) > 0
                        if mid < 1 or not user or (not text and not has_atts):
                            continue
                        msg: dict[str, Any] = {
                            "id": mid,
                            "username": user,
                            "text": text,
                            "ts": ts,
                        }
                        dest = row.get("to")
                        if dest is not None:
                            dest_s = str(dest).strip()
                            if dest_s:
                                msg["to"] = dest_s
                        kind = row.get("kind")
                        if kind:
                            msg["kind"] = str(kind)
                        pid = row.get("parent_id")
                        if pid is not None:
                            try:
                                pid_i = int(pid)
                                if pid_i > 0:
                                    msg["parent_id"] = pid_i
                            except (TypeError, ValueError):
                                pass
                        if has_atts:
                            msg["attachments"] = [a for a in atts if isinstance(a, dict)]
                        rx = row.get("reactions")
                        if isinstance(rx, dict):
                            msg["reactions"] = {
                                str(k): [str(u) for u in v if str(u).strip()]
                                for k, v in rx.items()
                                if isinstance(v, list)
                            }
                        _messages.append(msg)
                _next_id = max(_next_id, int(raw.get("next_id") or 1))
                if _messages:
                    _next_id = max(_next_id, max(int(m["id"]) for m in _messages) + 1)
                dels = raw.get("deletions")
                if isinstance(dels, list):
                    for row in dels:
                        if not isinstance(row, dict):
                            continue
                        ds = int(row.get("del_seq") or 0)
                        mid = int(row.get("message_id") or 0)
                        if ds < 1 or mid < 1:
                            continue
                        _deletions.append(
                            {
                                "del_seq": ds,
                                "message_id": mid,
                                "ts": float(row.get("ts") or 0),
                            }
                        )
                _del_seq = max(_del_seq, int(raw.get("del_seq") or 0))
                if _deletions:
                    _del_seq = max(_del_seq, max(int(d["del_seq"]) for d in _deletions))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    _loaded = True


def _ensure_loaded() -> None:
    with _lock:
        if not _loaded:
            _load_unlocked()


def _persist_unlocked() -> None:
    core.ensure_dirs()
    payload = {
        "version": 2,
        "next_id": _next_id,
        "messages": list(_messages),
        "deletions": list(_deletions[-MAX_DELETIONS_LOG:]),
        "del_seq": _del_seq,
    }
    json_atomic.atomic_write_json(PACK_CHAT_FILE, payload)


def _latest_message_id_unlocked() -> int:
    if not _messages:
        return 0
    return int(_messages[-1]["id"])


def touch_presence(username: str) -> None:
    user = str(username or "").strip()
    if not user:
        return
    now = time.time()
    with _lock:
        _presence[user] = now


def _presence_list_unlocked() -> list[dict[str, Any]]:
    now = time.time()
    roster = transfer.household_usernames()
    out: list[dict[str, Any]] = []
    for name in roster:
        ts = float(_presence.get(name) or 0)
        online = ts > 0 and (now - ts) < PRESENCE_TTL_SECONDS
        row: dict[str, Any] = {"username": name, "online": online}
        if online:
            row["last_seen"] = ts
        out.append(row)
    return out


def get_message(message_id: int) -> dict[str, Any]:
    _ensure_loaded()
    with _lock:
        for row in _messages:
            if int(row["id"]) == int(message_id):
                return dict(row)
    raise KeyError(str(message_id))


def _thread_key(row: dict[str, Any]) -> tuple:
    if is_pack_message(row):
        return ("pack",)
    sender = str(row.get("username") or "").strip()
    dest = _message_recipient(row) or ""
    if not dest:
        return ("pack",)
    return tuple(sorted([sender, dest]))


def _thread_key_user(user: str, dest: str | None) -> tuple:
    if not dest:
        return ("pack",)
    return tuple(sorted([str(user).strip(), str(dest).strip()]))


def _validate_parent(parent_id: int | None, user: str, dest: str | None) -> int | None:
    if parent_id is None:
        return None
    try:
        pid = int(parent_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid parent_id") from None
    if pid < 1:
        return None
    parent = get_message(pid)
    if parent.get("parent_id") is not None:
        raise ValueError("Cannot reply to a reply")
    if _thread_key(parent) != _thread_key_user(user, dest):
        raise ValueError("parent_id is not in this thread")
    if not visible_to(parent, user, is_admin=False):
        raise PermissionError("Cannot reply to this message")
    return pid


def append_message(
    username: str,
    text: str,
    *,
    to: str | None = None,
    parent_id: int | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> int:
    user = str(username or "").strip()
    if not user:
        raise ValueError("Username required")
    if is_virtual_sender(user):
        raise PermissionError("Forbidden")
    clean = sanitize_message(text)
    if not clean and not attachments:
        raise ValueError("Message or attachment required")
    if clean and len(clean) > MESSAGE_MAX_LEN:
        raise ValueError(f"Message too long (max {MESSAGE_MAX_LEN} characters)")
    dest: str | None = None
    if to is not None and str(to).strip():
        dest = _validate_dm_recipient(user, str(to).strip())
    if dest and is_virtual_peer(dest):
        if attachments:
            raise ValueError("Attachments not allowed in bot threads")
    if attachments:
        from . import pack_chat_enrich

        atts = pack_chat_enrich.validate_attachments_raw(
            user, attachments, dm_peer=dest
        )
    else:
        atts = []
    pid = _validate_parent(parent_id, user, dest)
    _ensure_loaded()
    now = time.time()
    global _next_id
    with _lock:
        mid = _next_id
        _next_id += 1
        row: dict[str, Any] = {"id": mid, "username": user, "text": clean or "", "ts": now}
        if dest:
            row["to"] = dest
        if pid:
            row["parent_id"] = pid
        if atts:
            row["attachments"] = atts
        _messages.append(row)
        _trim_messages_unlocked()
        _persist_unlocked()
        return mid


def toggle_reaction(message_id: int, actor: str, emoji: str) -> dict[str, Any]:
    who = str(actor or "").strip()
    key = str(emoji or "").strip().lower()
    if key not in ALLOWED_REACTIONS:
        raise ValueError("Unknown reaction")
    _ensure_loaded()
    with _lock:
        idx = next(
            (i for i, m in enumerate(_messages) if int(m["id"]) == int(message_id)), None
        )
        if idx is None:
            raise KeyError(str(message_id))
        row = _messages[idx]
        if not visible_to(row, who, is_admin=False):
            raise PermissionError("Forbidden")
        rx = row.get("reactions")
        if not isinstance(rx, dict):
            rx = {}
        users = list(rx.get(key) or [])
        if who in users:
            users = [u for u in users if u != who]
        else:
            users = users + [who]
        if users:
            rx[key] = users
        elif key in rx:
            del rx[key]
        row["reactions"] = rx
        _messages[idx] = row
        _persist_unlocked()
        return dict(row)


def claim_attachment_copy(message_id: int, attachment_index: int, claimer: str) -> dict[str, Any]:
    who = str(claimer or "").strip()
    _ensure_loaded()
    from . import transfer

    with _lock:
        idx = next(
            (i for i, m in enumerate(_messages) if int(m["id"]) == int(message_id)), None
        )
        if idx is None:
            raise KeyError(str(message_id))
        row = _messages[idx]
        if not visible_to(row, who, is_admin=False):
            raise PermissionError("Forbidden")
        atts = row.get("attachments")
        if not isinstance(atts, list):
            raise ValueError("No attachments")
        ai = int(attachment_index)
        if ai < 0 or ai >= len(atts):
            raise ValueError("Invalid attachment index")
        att = atts[ai]
        if not isinstance(att, dict) or att.get("type") != "library_book":
            raise ValueError("Not a book attachment")
        if str(att.get("intent")) != "offer_copy":
            raise ValueError("Copy not offered")
        if att.get("claimed_by"):
            raise ValueError("Copy already claimed")
        owner = str(att.get("owner") or "")
        item_id = str(att.get("item_id") or "")
        if not owner or not item_id or owner == who:
            raise ValueError("Invalid attachment")
    item = transfer.send_library_item(owner, who, item_id)
    with _lock:
        row = next(m for m in _messages if int(m["id"]) == int(message_id))
        atts = list(row.get("attachments") or [])
        att = dict(atts[ai])
        att["claimed_by"] = who
        atts[ai] = att
        row["attachments"] = atts
        _persist_unlocked()
    return {"item": item, "attachment": att}


def append_virtual_dm(
    from_bot: str, to_user: str, text: str, *, kind: str = "system"
) -> int:
    sender = _canonical_virtual_peer(from_bot)
    if not sender:
        raise ValueError("Invalid bot")
    dest = str(to_user or "").strip()
    if not dest:
        raise ValueError("Recipient required")
    row = accounts.get_user(dest)
    if not row or not row.get("enabled", True):
        raise ValueError("Unknown user")
    clean = sanitize_message(text)
    if not clean:
        raise ValueError("Message required")
    if len(clean) > MESSAGE_MAX_LEN:
        clean = clean[:MESSAGE_MAX_LEN]
    _ensure_loaded()
    now = time.time()
    global _next_id
    with _lock:
        mid = _next_id
        _next_id += 1
        _messages.append(
            {
                "id": mid,
                "username": sender,
                "to": dest,
                "text": clean,
                "ts": now,
                "kind": str(kind or "system"),
            }
        )
        _trim_messages_unlocked()
        _persist_unlocked()
        return mid


def append_system_dm(to_user: str, text: str, *, kind: str = "scheduled_sniff") -> int:
    return append_virtual_dm(SYSTEM_SENDER, to_user, text, kind=kind)


def delete_message(message_id: int, actor: str, *, is_admin: bool) -> None:
    who = str(actor or "").strip()
    if not who:
        raise PermissionError("Forbidden")
    _ensure_loaded()
    with _lock:
        idx = next((i for i, m in enumerate(_messages) if int(m["id"]) == int(message_id)), None)
        if idx is None:
            raise KeyError(str(message_id))
        row = _messages[idx]
        sender = str(row.get("username") or "").strip()
        dest = _message_recipient(row)
        if is_virtual_sender(sender):
            allowed = is_admin or who == dest
        elif dest:
            allowed = is_admin or who == sender
        else:
            allowed = is_admin or who == sender
        if not allowed:
            raise PermissionError("Forbidden")
        global _del_seq
        _del_seq += 1
        _deletions.append(
            {"del_seq": _del_seq, "message_id": int(message_id), "ts": time.time()}
        )
        if len(_deletions) > MAX_DELETIONS_LOG:
            _deletions[:] = _deletions[-MAX_DELETIONS_LOG:]
        _messages.pop(idx)
        _persist_unlocked()


def _is_dm_with_bot(row: dict[str, Any], viewer: str, bot: str) -> bool:
    if is_pack_message(row):
        return False
    sender = str(row.get("username") or "").strip()
    dest = _message_recipient(row) or ""
    if sender == viewer and dest == bot:
        return True
    if sender == bot and dest == viewer:
        return True
    return False


def clear_bot_dm_thread(viewer: str, bot: str) -> list[int]:
    """Remove all DMs between viewer and a virtual bot (viewer-only)."""
    who = str(viewer or "").strip()
    peer = _canonical_virtual_peer(bot)
    if not peer or peer == SYSTEM_SENDER:
        raise ValueError("Invalid bot")
    if not who:
        raise ValueError("Username required")
    _ensure_loaded()
    with _lock:
        ids: list[int] = []
        global _del_seq
        now = time.time()
        keep: list[dict[str, Any]] = []
        for row in _messages:
            if _is_dm_with_bot(row, who, peer):
                mid = int(row["id"])
                ids.append(mid)
                _del_seq += 1
                _deletions.append({"del_seq": _del_seq, "message_id": mid, "ts": now})
            else:
                keep.append(row)
        if ids:
            _messages[:] = keep
            if len(_deletions) > MAX_DELETIONS_LOG:
                _deletions[:] = _deletions[-MAX_DELETIONS_LOG:]
            _persist_unlocked()
        return ids


def clear_messages() -> list[int]:
    """Remove pack-channel messages only (admin). Returns deleted message ids."""
    _ensure_loaded()
    with _lock:
        pack_rows = [m for m in _messages if is_pack_message(m)]
        ids = [int(m["id"]) for m in pack_rows]
        global _del_seq
        now = time.time()
        for mid in ids:
            _del_seq += 1
            _deletions.append({"del_seq": _del_seq, "message_id": mid, "ts": now})
        _messages[:] = [m for m in _messages if not is_pack_message(m)]
        if len(_deletions) > MAX_DELETIONS_LOG:
            _deletions[:] = _deletions[-MAX_DELETIONS_LOG:]
        _persist_unlocked()
        return ids


def _list_dm_peers_unlocked(viewer: str, *, is_admin: bool = False) -> list[dict[str, Any]]:
    who = str(viewer or "").strip()
    if not who:
        return []
    by_peer: dict[str, dict[str, Any]] = {}
    for row in _messages:
            if not visible_to(row, who, is_admin=is_admin) or is_pack_message(row):
                continue
            sender = str(row.get("username") or "").strip()
            dest = _message_recipient(row) or ""
            if is_virtual_sender(sender):
                if who != dest:
                    continue
                peer = sender
            elif sender == who:
                peer = dest
            elif dest == who:
                peer = sender
            else:
                continue
            if not peer or peer == who:
                continue
            ts = float(row.get("ts") or 0)
            prev = by_peer.get(peer)
            system = is_virtual_sender(sender)
            if prev is None or ts >= float(prev.get("last_ts") or 0):
                by_peer[peer] = {
                    "username": peer,
                    "last_ts": ts,
                    "system": system or bool(prev and prev.get("system")),
                }
            elif system:
                by_peer[peer]["system"] = True
    return sorted(by_peer.values(), key=lambda r: float(r.get("last_ts") or 0), reverse=True)


def list_dm_peers(viewer: str, *, is_admin: bool = False) -> list[dict[str, Any]]:
    _ensure_loaded()
    with _lock:
        return _list_dm_peers_unlocked(viewer, is_admin=is_admin)


def snapshot(
    after: int = 0,
    del_after: int = 0,
    *,
    touch_user: str | None = None,
    viewer: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    _ensure_loaded()
    if touch_user:
        touch_presence(touch_user)
    who = str(viewer or touch_user or "").strip()
    from . import pack_chat_enrich

    with _lock:
        parent_cache = {int(m["id"]): m for m in _messages}
        raw_msgs = [
            m
            for m in _messages
            if int(m["id"]) > int(after) and (not who or visible_to(m, who, is_admin=is_admin))
        ]
        msgs = [
            pack_chat_enrich.enrich_message(_row_out(m), who, parent_cache) for m in raw_msgs
        ]
        removed = [
            int(d["message_id"])
            for d in _deletions
            if int(d["del_seq"]) > int(del_after)
        ]
        peers = _list_dm_peers_unlocked(who, is_admin=is_admin) if who else []
        return {
            "messages": msgs,
            "latest_id": _latest_message_id_unlocked(),
            "removed": removed,
            "latest_del_seq": _del_seq,
            "presence": _presence_list_unlocked(),
            "peers": peers,
        }