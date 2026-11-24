"""Parse xdcc bot SLOTS/banner lines for stale and capacity hints."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass

_SLOTS_NUMERIC_RE = re.compile(r"^SLOTS\s+(\d+)\s+(\d+)\b", re.IGNORECASE)
_TYPE_BOT_RE = re.compile(r"Type:\s*@([A-Za-z0-9][A-Za-z0-9_-]*)", re.IGNORECASE)
_SLOTS_BANNER_RE = re.compile(r"Slots:\s*(\d+)\s*/\s*(\d+)", re.IGNORECASE)
_QUEUED_RE = re.compile(r"Queued:\s*(\d+)", re.IGNORECASE)
_TRAILING_BOT_RE = re.compile(
    r"@([A-Za-z0-9][A-Za-z0-9_-]*)\s+For\s+My\s+List",
    re.IGNORECASE,
)


@dataclass
class BotHealth:
    last_seen: float
    slots_free: int | None = None
    slots_total: int | None = None
    queued: int | None = None


class BotHealthTracker:
    def __init__(self, stale_seconds: float) -> None:
        self.stale_seconds = stale_seconds
        self._lock = threading.Lock()
        self._bots: dict[str, BotHealth] = {}
        self._last_type_bot: str | None = None

    def _touch(
        self,
        bot: str,
        *,
        slots_free: int | None = None,
        slots_total: int | None = None,
        queued: int | None = None,
    ) -> None:
        key = bot.lower()
        now = time.time()
        with self._lock:
            entry = self._bots.get(key)
            if entry is None:
                entry = BotHealth(last_seen=now)
                self._bots[key] = entry
            entry.last_seen = now
            if slots_free is not None:
                entry.slots_free = slots_free
            if slots_total is not None:
                entry.slots_total = slots_total
            if queued is not None:
                entry.queued = queued

    def ingest_channel_message(self, text: str) -> None:
        msg = (text or "").strip()
        if not msg:
            return
        bot: str | None = None
        tm = _TYPE_BOT_RE.search(msg)
        if tm:
            bot = tm.group(1).lower()
            with self._lock:
                self._last_type_bot = bot
        if not bot:
            tb = _TRAILING_BOT_RE.search(msg)
            if tb:
                bot = tb.group(1).lower()
        slots_m = _SLOTS_BANNER_RE.search(msg)
        queued_m = _QUEUED_RE.search(msg)
        if slots_m or queued_m or tm or tb:
            if not bot:
                with self._lock:
                    bot = self._last_type_bot
            if bot:
                self._touch(
                    bot,
                    slots_free=int(slots_m.group(1)) if slots_m else None,
                    slots_total=int(slots_m.group(2)) if slots_m else None,
                    queued=int(queued_m.group(1)) if queued_m else None,
                )
        num = _SLOTS_NUMERIC_RE.match(msg)
        if num:
            with self._lock:
                bot = self._last_type_bot
            if not bot:
                parts = msg.split()
                if len(parts) >= 2:
                    bot = parts[-2].lower()
            if bot:
                self._touch(
                    bot,
                    slots_free=int(num.group(1)),
                    slots_total=int(num.group(2)),
                )

    def is_stale(self, bot_nick: str) -> bool:
        key = (bot_nick or "").strip().lower()
        if not key:
            return False
        with self._lock:
            entry = self._bots.get(key)
            if entry is None:
                return False
            return (time.time() - entry.last_seen) > self.stale_seconds

    def warn_full_slots(self, bot_nick: str) -> str | None:
        key = (bot_nick or "").strip().lower()
        with self._lock:
            entry = self._bots.get(key)
            if not entry:
                return None
            if entry.slots_free == 0 and entry.slots_total:
                q = entry.queued if entry.queued is not None else 0
                return f"Warning: {bot_nick} shows 0/{entry.slots_total} free slots (queued {q})."
        return None