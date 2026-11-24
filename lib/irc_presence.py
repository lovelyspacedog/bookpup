"""Track channel NAME list for IRC bot preflight."""

from __future__ import annotations

import re
import threading
import time

_NICK_PREFIX_RE = re.compile(r"^[@+%&~]*")
_353_RE = re.compile(
    r"(?:^|\s)353\s+\S+\s+[=@%*]\s*(\S+)\s+:(.*)$",
    re.IGNORECASE,
)
_366_RE = re.compile(r"(?:^|\s)366\s+\S+\s+(\S+)\s+:", re.IGNORECASE)
_JOIN_RE = re.compile(
    r"^:(?P<nick>[^! ]+)!.*\sJOIN\s+:?(?P<channel>\S+)",
    re.IGNORECASE,
)
_PART_RE = re.compile(
    r"^:(?P<nick>[^! ]+)!.*\sPART\s+(?P<channel>\S+)",
    re.IGNORECASE,
)
_QUIT_RE = re.compile(r"^:(?P<nick>[^! ]+)!.*\sQUIT\b", re.IGNORECASE)
_KICK_RE = re.compile(
    r"^\S+\s+KICK\s+(?P<channel>\S+)\s+(?P<nick>\S+)",
    re.IGNORECASE,
)
_NICK_CHANGE_RE = re.compile(
    r"^:(?P<old>[^! ]+)!.*\sNICK\s+:(?P<new>\S+)",
    re.IGNORECASE,
)


def normalize_channel(channel: str) -> str:
    ch = (channel or "").strip().lower()
    if ch and not ch.startswith("#"):
        ch = f"#{ch}"
    return ch


def strip_nick_prefix(nick: str) -> str:
    return _NICK_PREFIX_RE.sub("", (nick or "").strip()).lower()


class ChannelPresence:
    def __init__(self, tracked: tuple[str, ...] = ()) -> None:
        self._lock = threading.Lock()
        self._nicks: dict[str, set[str]] = {}
        self._names_ready: dict[str, threading.Event] = {}
        self._names_pending: dict[str, bool] = {}
        for ch in tracked:
            self.track_channel(ch)

    def track_channel(self, channel: str) -> None:
        ch = normalize_channel(channel)
        with self._lock:
            self._nicks.setdefault(ch, set())
            if ch not in self._names_ready:
                self._names_ready[ch] = threading.Event()

    def mark_names_start(self, channel: str) -> None:
        ch = normalize_channel(channel)
        with self._lock:
            self._nicks[ch] = set()
            self._names_pending[ch] = True
            ev = self._names_ready.setdefault(ch, threading.Event())
            ev.clear()

    def add_names(self, channel: str, raw_nicks: str) -> None:
        ch = normalize_channel(channel)
        parts = (raw_nicks or "").split()
        with self._lock:
            bucket = self._nicks.setdefault(ch, set())
            for nick in parts:
                n = strip_nick_prefix(nick)
                if n:
                    bucket.add(n)

    def end_names(self, channel: str) -> None:
        ch = normalize_channel(channel)
        with self._lock:
            self._names_pending[ch] = False
            ev = self._names_ready.get(ch)
            if ev:
                ev.set()

    def nick_joined(self, channel: str, nick: str) -> None:
        ch = normalize_channel(channel)
        n = strip_nick_prefix(nick)
        if not n:
            return
        with self._lock:
            self._nicks.setdefault(ch, set()).add(n)

    def nick_parted(self, channel: str, nick: str) -> None:
        ch = normalize_channel(channel)
        n = strip_nick_prefix(nick)
        with self._lock:
            self._nicks.get(ch, set()).discard(n)

    def nick_quit(self, nick: str) -> None:
        n = strip_nick_prefix(nick)
        if not n:
            return
        with self._lock:
            for bucket in self._nicks.values():
                bucket.discard(n)

    def nick_kicked(self, channel: str, nick: str) -> None:
        self.nick_parted(channel, nick)

    def nick_renamed(self, old: str, new: str) -> None:
        o, nn = strip_nick_prefix(old), strip_nick_prefix(new)
        with self._lock:
            for bucket in self._nicks.values():
                if o in bucket:
                    bucket.discard(o)
                    bucket.add(nn)

    def is_in_channel(self, channel: str, nick: str) -> bool:
        ch = normalize_channel(channel)
        n = strip_nick_prefix(nick)
        with self._lock:
            return n in self._nicks.get(ch, set())

    def is_tracked_channel(self, channel: str) -> bool:
        ch = normalize_channel(channel)
        with self._lock:
            return ch in self._nicks

    def wait_names_ready(self, channel: str, timeout: float = 5.0) -> bool:
        ch = normalize_channel(channel)
        self.track_channel(ch)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                ev = self._names_ready.get(ch)
            if ev and ev.is_set():
                return True
            time.sleep(0.05)
        with self._lock:
            ev = self._names_ready.get(ch)
            if ev and ev.is_set():
                return True
        return False

    def handle_server_line(self, line: str) -> None:
        text = (line or "").strip("\r\n")
        m353 = _353_RE.search(text)
        if m353:
            ch = normalize_channel(m353.group(1))
            with self._lock:
                pending = self._names_pending.get(ch)
            if not pending:
                self.mark_names_start(m353.group(1))
            self.add_names(m353.group(1), m353.group(2))
            return
        m366 = _366_RE.search(text)
        if m366:
            self.end_names(m366.group(1))
            return
        mj = _JOIN_RE.match(text)
        if mj:
            self.nick_joined(mj.group("channel"), mj.group("nick"))
            return
        mp = _PART_RE.match(text)
        if mp:
            self.nick_parted(mp.group("channel"), mp.group("nick"))
            return
        mq = _QUIT_RE.match(text)
        if mq:
            self.nick_quit(mq.group("nick"))
            return
        mk = _KICK_RE.match(text)
        if mk:
            self.nick_kicked(mk.group("channel"), mk.group("nick"))
            return
        mn = _NICK_CHANGE_RE.match(text)
        if mn:
            self.nick_renamed(mn.group("old"), mn.group("new"))