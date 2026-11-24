"""FeatureCat — feature ideas via Pack chat → admin feature inbox."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

from . import accounts
from . import bot_reply
from . import core
from . import json_atomic
from . import pack_chat

FEATURECAT_SENDER = pack_chat.FEATURECAT_SENDER
STATE_FILE = core.CONFIG_DIR / "featurecat_state.json"
INBOX_FILE = core.CONFIG_DIR / "feature_inbox.json"
MAX_INBOX = 200

INTRO_TEXT = (
    "Hi — I'm FeatureCat. Share ideas for new tools or improvements "
    "(one wish per message is fine). "
    "Say what you want and why it would help your pack. "
    "Your household admin sees requests on Pack roster → Feature inbox. "
    "I'll reply here when your idea is saved."
)
ACK_TEXT = "Got it — your feature idea is in the admin feature inbox. Thanks for pitching in."

_lock = threading.Lock()
_state_loaded = False
_intro_seen: set[str] = set()

_inbox_loaded = False
_inbox_reports: list[dict[str, Any]] = []
_inbox_next_id = 1


def _load_state_unlocked() -> None:
    global _state_loaded, _intro_seen
    _intro_seen = set()
    if STATE_FILE.is_file():
        try:
            raw = json.loads(STATE_FILE.read_text())
            if isinstance(raw, dict):
                rows = raw.get("intro_seen")
                if isinstance(rows, list):
                    for name in rows:
                        s = str(name or "").strip()
                        if s:
                            _intro_seen.add(s)
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    _state_loaded = True


def _persist_state_unlocked() -> None:
    core.ensure_dirs()
    json_atomic.atomic_write_json(
        STATE_FILE,
        {"version": 1, "intro_seen": sorted(_intro_seen)},
    )


def _ensure_state() -> None:
    with _lock:
        if not _state_loaded:
            _load_state_unlocked()


def _load_inbox_unlocked() -> None:
    global _inbox_loaded, _inbox_reports, _inbox_next_id
    _inbox_reports = []
    _inbox_next_id = 1
    if INBOX_FILE.is_file():
        try:
            raw = json.loads(INBOX_FILE.read_text())
            if isinstance(raw, dict):
                rows = raw.get("reports")
                if isinstance(rows, list):
                    for row in rows:
                        if not isinstance(row, dict):
                            continue
                        rid = int(row.get("id") or 0)
                        who = str(row.get("from") or "").strip()
                        text = str(row.get("text") or "").strip()
                        ts = float(row.get("ts") or 0)
                        if rid < 1 or not who or not text:
                            continue
                        item: dict[str, Any] = {
                            "id": rid,
                            "from": who,
                            "text": text,
                            "ts": ts,
                        }
                        mid = row.get("pack_message_id")
                        if mid is not None:
                            item["pack_message_id"] = int(mid)
                        _inbox_reports.append(item)
                _inbox_next_id = max(_inbox_next_id, int(raw.get("next_id") or 1))
                if _inbox_reports:
                    _inbox_next_id = max(
                        _inbox_next_id, max(int(r["id"]) for r in _inbox_reports) + 1
                    )
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    _inbox_loaded = True


def _persist_inbox_unlocked() -> None:
    core.ensure_dirs()
    json_atomic.atomic_write_json(
        INBOX_FILE,
        {
            "version": 1,
            "next_id": _inbox_next_id,
            "reports": list(_inbox_reports),
        },
    )


def _ensure_inbox() -> None:
    with _lock:
        if not _inbox_loaded:
            _load_inbox_unlocked()


def ensure_intro(viewer: str) -> bool:
    who = str(viewer or "").strip()
    if not who:
        return False
    row = accounts.get_user(who)
    if not row or not row.get("enabled", True):
        return False
    _ensure_state()
    with _lock:
        if who in _intro_seen:
            return False
        _intro_seen.add(who)
        _persist_state_unlocked()
    bot_reply.schedule_delayed_virtual_dm(
        FEATURECAT_SENDER, who, INTRO_TEXT, kind="featurecat_intro"
    )
    return True


def on_user_submission(
    from_user: str, text: str, *, pack_message_id: int | None = None
) -> int:
    who = str(from_user or "").strip()
    clean = pack_chat.sanitize_message(text)
    if not who or not clean:
        raise ValueError("Submission required")
    _ensure_inbox()
    now = time.time()
    global _inbox_next_id
    with _lock:
        rid = _inbox_next_id
        _inbox_next_id += 1
        row: dict[str, Any] = {
            "id": rid,
            "from": who,
            "text": clean,
            "ts": now,
        }
        if pack_message_id is not None:
            row["pack_message_id"] = int(pack_message_id)
        _inbox_reports.append(row)
        while len(_inbox_reports) > MAX_INBOX:
            _inbox_reports.pop(0)
        _persist_inbox_unlocked()
    bot_reply.schedule_delayed_virtual_dm(
        FEATURECAT_SENDER, who, ACK_TEXT, kind="featurecat_ack"
    )
    return rid


def list_inbox() -> list[dict[str, Any]]:
    _ensure_inbox()
    with _lock:
        return sorted(
            (dict(r) for r in _inbox_reports),
            key=lambda r: float(r.get("ts") or 0),
            reverse=True,
        )


def dismiss_submission(submission_id: int) -> None:
    _ensure_inbox()
    with _lock:
        idx = next(
            (
                i
                for i, r in enumerate(_inbox_reports)
                if int(r["id"]) == int(submission_id)
            ),
            None,
        )
        if idx is None:
            raise KeyError(str(submission_id))
        _inbox_reports.pop(idx)
        _persist_inbox_unlocked()