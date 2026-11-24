"""Household pack chat (persisted messages, in-memory presence)."""

from __future__ import annotations

import json
import re
import threading
import time
from typing import Any

from . import core
from . import json_atomic
from . import transfer

PACK_CHAT_FILE = core.CONFIG_DIR / "pack_chat.json"
MAX_MESSAGES = 500
MAX_DELETIONS_LOG = 200
PRESENCE_TTL_SECONDS = 90
MESSAGE_MAX_LEN = 2000

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
                        if mid < 1 or not user or not text:
                            continue
                        _messages.append(
                            {"id": mid, "username": user, "text": text, "ts": ts}
                        )
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
        "version": 1,
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


def append_message(username: str, text: str) -> int:
    user = str(username or "").strip()
    if not user:
        raise ValueError("Username required")
    clean = sanitize_message(text)
    if not clean:
        raise ValueError("Message required")
    if len(clean) > MESSAGE_MAX_LEN:
        raise ValueError(f"Message too long (max {MESSAGE_MAX_LEN} characters)")
    _ensure_loaded()
    now = time.time()
    global _next_id
    with _lock:
        mid = _next_id
        _next_id += 1
        _messages.append({"id": mid, "username": user, "text": clean, "ts": now})
        _trim_messages_unlocked()
        _persist_unlocked()
        return mid


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
        owner = str(row.get("username") or "").strip()
        if owner != who and not is_admin:
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


def clear_messages() -> list[int]:
    """Remove all messages (admin). Returns deleted message ids."""
    _ensure_loaded()
    with _lock:
        ids = [int(m["id"]) for m in _messages]
        global _del_seq
        now = time.time()
        for mid in ids:
            _del_seq += 1
            _deletions.append({"del_seq": _del_seq, "message_id": mid, "ts": now})
        _messages.clear()
        if len(_deletions) > MAX_DELETIONS_LOG:
            _deletions[:] = _deletions[-MAX_DELETIONS_LOG:]
        _persist_unlocked()
        return ids


def snapshot(
    after: int = 0,
    del_after: int = 0,
    *,
    touch_user: str | None = None,
) -> dict[str, Any]:
    _ensure_loaded()
    if touch_user:
        touch_presence(touch_user)
    with _lock:
        msgs = [dict(m) for m in _messages if int(m["id"]) > int(after)]
        removed = [
            int(d["message_id"])
            for d in _deletions
            if int(d["del_seq"]) > int(del_after)
        ]
        return {
            "messages": msgs,
            "latest_id": _latest_message_id_unlocked(),
            "removed": removed,
            "latest_del_seq": _del_seq,
            "presence": _presence_list_unlocked(),
        }