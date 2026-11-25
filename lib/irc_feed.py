"""In-memory IRC activity feed for the live preview panel."""

from __future__ import annotations

import re
import threading
import time
from collections import deque
from typing import Any

_MAX = 400
_lock = threading.Lock()
_events: deque[dict[str, Any]] = deque(maxlen=_MAX)
_seq = 0
_owner = threading.local()

_CTRL_RE = re.compile(r"[\x00-\x09\x0b-\x1f\x7f]")
_MIRC_COLOR_RE = re.compile(r"\x03\d{0,2}(?:,\d{0,2})?|\x02|\x1d|\x1f|\x16|\x0f")


def strip_irc(text: str) -> str:
    text = _MIRC_COLOR_RE.sub("", text)
    text = text.replace("\x01", "")
    return _CTRL_RE.sub("", text).strip()


def set_job_owner(owner: str | None) -> None:
    if owner:
        _owner.username = str(owner).strip()
    elif hasattr(_owner, "username"):
        delattr(_owner, "username")


def _active_owner(explicit: str | None) -> str | None:
    if explicit:
        return str(explicit).strip() or None
    return getattr(_owner, "username", None)


def append(
    *,
    direction: str,
    kind: str,
    text: str,
    target: str | None = None,
    owner: str | None = None,
) -> int:
    global _seq
    clean = strip_irc(text)
    if not clean and kind not in ("session", "dcc"):
        return _seq
    with _lock:
        _seq += 1
        who = _active_owner(owner)
        ev = {
            "id": _seq,
            "ts": time.time(),
            "dir": direction,
            "kind": kind,
            "target": target,
            "text": clean,
        }
        if who:
            ev["owner"] = who
        _events.append(ev)
        return _seq


def append_out(target: str, text: str) -> None:
    append(direction="out", kind="privmsg", text=text, target=target)


def append_in_line(raw_line: str, *, owner: str | None = None) -> None:
    text = raw_line
    direction = "in"
    kind = "raw"
    target = None
    if "PRIVMSG" in raw_line:
        kind = "privmsg"
        m = re.search(r"PRIVMSG\s+(\S+)\s+:(.*)$", raw_line)
        if m:
            target = m.group(1)
            text = m.group(2)
    elif " NOTICE " in raw_line:
        kind = "notice"
        m = re.search(r"NOTICE\s+(\S+)\s+:(.*)$", raw_line)
        if m:
            target = m.group(1)
            text = m.group(2)
    elif " JOIN " in raw_line:
        kind = "session"
        m = re.search(r":\S+!", raw_line)
        text = "joined channel" if m else raw_line
    elif raw_line.startswith(":") and " 00" in raw_line:
        kind = "session"
        text = raw_line.split(":", 2)[-1] if raw_line.count(":") >= 2 else raw_line
    elif "DCC SEND" in raw_line.upper():
        kind = "dcc"
        text = re.sub(r"\x01", "", text)
    append(direction=direction, kind=kind, text=text, target=target, owner=owner)


def append_session(message: str, *, owner: str | None = None) -> None:
    append(direction="sys", kind="session", text=message, target=None, owner=owner)


def current_seq() -> int:
    with _lock:
        return _seq


def events_for_failure(
    *,
    owner: str | None,
    since_id: int = 0,
    since_ts: float = 0,
) -> list[dict[str, Any]]:
    """IRC feed lines relevant to a failed fetch (job owner + untagged reader lines)."""
    who = str(owner or "").strip() or None
    sid = max(0, int(since_id))
    sts = float(since_ts or 0)
    with _lock:
        items = list(_events)
    out: list[dict[str, Any]] = []
    for ev in items:
        eid = int(ev.get("id") or 0)
        if eid <= sid:
            continue
        ev_ts = float(ev.get("ts") or 0)
        if sts > 0 and ev_ts + 1.0 < sts:
            continue
        ev_owner = ev.get("owner")
        if ev_owner and who and str(ev_owner) != who:
            continue
        out.append(dict(ev))
    return out


def snapshot(after: int = 0, limit: int = 150, viewer: str | None = None) -> dict:
    with _lock:
        items = [e for e in list(_events) if int(e["id"]) > after]
    if viewer:
        who = str(viewer).strip()
        if who:
            # Reader-thread IRC lines often have no owner tag; show those to every signed-in pup.
            items = [e for e in items if not e.get("owner") or e.get("owner") == who]
    if limit > 0 and len(items) > limit:
        items = items[-limit:]
    return {"events": items, "latest_id": _seq}