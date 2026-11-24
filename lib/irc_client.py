"""Minimal IRC client with DCC SEND receive (outbound TCP to sender)."""

from __future__ import annotations

import random
import re
import socket
import ssl
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable

from . import irc_feed
from .core import (
    BOOK_OFFER_EXTEND_SECONDS,
    BOOK_OFFER_MAX_SECONDS,
    DEFAULT_CHANNELS,
    DOWNLOAD_TIMEOUT,
    IRC_POST_JOIN_COOLDOWN,
    SEARCH_TIMEOUT,
    bot_status_stale_seconds,
    download_offer_timeout,
)
from .irc_bot_health import BotHealthTracker
from .irc_commands import serving_bot_nick
from .irc_nicks import random_nick as pick_irc_nick
from .irc_presence import ChannelPresence, normalize_channel

_NOTICE_TRAILING_RE = re.compile(r"NOTICE\s+\S+\s+:(.*)$", re.IGNORECASE)
_PRIVMSG_TRAILING_RE = re.compile(r"PRIVMSG\s+\S+\s+:(.*)$", re.IGNORECASE)
_NOTICE_TARGET_RE = re.compile(r"NOTICE\s+(\S+)\s+:", re.IGNORECASE)
_PRIVMSG_TARGET_RE = re.compile(r"PRIVMSG\s+(\S+)\s+:", re.IGNORECASE)

SEARCH_NO_MATCHES_RE = re.compile(
    r"(?:returned\s+no\s+matches|no\s+matches\s+found|\b0\s+matches\b)",
    re.IGNORECASE,
)
# Undernet #bookz: per-catalogue zeros are interim; SearchBot may still return hits.
CATALOG_ZERO_MATCHES_RE = re.compile(
    r"\b0\s+matches\s+in\s+the\s+.+\s+catalog(?:ue)?\b",
    re.IGNORECASE,
)
SEARCH_QUERY_IN_NOTICE_RE = re.compile(
    r"search for\s+[\"“\u201c]([^\"”\u201d]+)[\"”\u201d]",
    re.IGNORECASE,
)
_PREFIX_NICK_RE = re.compile(r"^:([^! ]+)")
BOOK_ACTIVITY_RE = re.compile(
    r"\b(searching for|please wait|queued|sending|packing|preparing)\b",
    re.IGNORECASE,
)


def irc_prefix_nick(line: str) -> str | None:
    m = _PREFIX_NICK_RE.match((line or "").strip())
    if not m:
        return None
    return m.group(1).lower()


def irc_trailing_message(line: str) -> str:
    line = line.strip("\r\n")
    m = _NOTICE_TRAILING_RE.search(line) or _PRIVMSG_TRAILING_RE.search(line)
    if m:
        return irc_feed.strip_irc(m.group(1))
    if line.count(":") >= 2:
        return irc_feed.strip_irc(line.split(":", 2)[-1])
    return irc_feed.strip_irc(line)


def _norm_search_query(query: str) -> str:
    return " ".join(query.strip().lower().split())


def _normalize_irc_target(raw: str) -> str:
    t = (raw or "").lstrip(":").strip()
    if t.startswith("@"):
        t = t[1:]
    return t.lower()


def is_search_no_matches_notice(message: str) -> bool:
    """True when SearchBot (or similar) reports an empty @search result."""
    text = (message or "").strip()
    if not text:
        return False
    if CATALOG_ZERO_MATCHES_RE.search(text):
        return False
    if not SEARCH_NO_MATCHES_RE.search(text):
        return False
    if re.search(r"\b0\s+matches\b", text, re.IGNORECASE) and re.search(
        r"\bcatalog(?:ue)?\b", text, re.IGNORECASE
    ):
        return False
    return True


def extract_search_query_from_notice(message: str) -> str | None:
    m = SEARCH_QUERY_IN_NOTICE_RE.search(message or "")
    if not m:
        return None
    return m.group(1).strip()


class SearchNoMatchesError(Exception):
    """IRC search finished with no DCC results file."""


class DownloadRequestError(Exception):
    """IRC bots refused or cannot fulfill a download command."""


DOWNLOAD_FAIL_NOTICE_RE = re.compile(
    r"file not found in the licensed catalog(?:ue)?|"
    r"not available in the licensed catalog(?:ue)?|"
    r"(?:has|have)\s+no\s+epub\s+available|"
    r"no\s+epub\s+available",
    re.IGNORECASE,
)


def is_catalog_zero_matches_notice(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(CATALOG_ZERO_MATCHES_RE.search(text))


def is_download_failure_notice(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    return bool(DOWNLOAD_FAIL_NOTICE_RE.search(text))


def is_fetch_abort_notice(message: str) -> bool:
    """Terminate a book DCC wait (fetch); excludes interim catalogue zeros during @search."""
    text = (message or "").strip()
    if not text:
        return False
    if is_download_failure_notice(text):
        return True
    return is_catalog_zero_matches_notice(text)


def is_search_results_dcc_filename(filename: str) -> bool:
    fn = (filename or "").lower()
    return "searchbot_results" in fn or fn.endswith(".txt.zip")


def _parse_dcc_payload(payload: str) -> DccOffer | None:
    text = payload.strip().strip("\x01")
    if not text.upper().startswith("DCC SEND"):
        return None
    parts = text[8:].strip().split()
    if len(parts) < 4:
        return None
    try:
        size = int(parts[-1])
        port = int(parts[-2])
    except ValueError:
        return None
    host = _dcc_host(parts[-3])
    filename = " ".join(parts[:-3])
    if not filename:
        return None
    return DccOffer(filename=filename, host=host, port=port, size=size)


@dataclass
class DccOffer:
    filename: str
    host: str
    port: int
    size: int


def _dcc_host(raw: str) -> str:
    if re.fullmatch(r"\d+", raw):
        n = int(raw)
        return ".".join(str((n >> shift) & 0xFF) for shift in (24, 16, 8, 0))
    return raw


def random_nick() -> str:
    return pick_irc_nick()


class IrcSession:
    def __init__(
        self,
        server: str,
        port: int,
        *,
        use_tls: bool = False,
        nick: str | None = None,
        channels: tuple[str, ...] = DEFAULT_CHANNELS,
        on_notice: Callable[[str], None] | None = None,
        on_search_no_match: Callable[[str, str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
    ) -> None:
        self.server = server
        self.port = port
        self.use_tls = use_tls
        self.nick = nick or random_nick()
        self.channels = channels
        self.on_notice = on_notice or (lambda _m: None)
        self.on_search_no_match = on_search_no_match or (lambda _q, _r: None)
        self.on_status = on_status
        self._sock: socket.socket | None = None
        self._reader: threading.Thread | None = None
        self._stop = threading.Event()
        self._dcc_cond = threading.Condition()
        self._pending_dcc: list[DccOffer] = []
        self._connected = threading.Event()
        self._alive = threading.Event()
        self._search_aborted = threading.Event()
        self._search_abort_reason: str | None = None
        self._no_match_queries: set[str] = set()
        self._awaiting_search_dcc = False
        self._awaiting_book_dcc = False
        self._book_aborted = threading.Event()
        self._book_abort_reason: str | None = None
        self._active_search_query: str | None = None
        self._channel_ready_at: float = 0.0
        self.last_error: str | None = None
        self.feed_owner: str | None = None
        self._presence = ChannelPresence(channels)
        self._health = BotHealthTracker(bot_status_stale_seconds())
        self._active_book_bot: str | None = None
        self._book_offer_deadline: float = 0.0

    def status(self, message: str) -> None:
        text = irc_feed.strip_irc(str(message or ""))
        if not text:
            return
        irc_feed.append_session(text, owner=self.feed_owner)
        if self.on_status:
            try:
                self.on_status(text)
            except Exception:
                pass

    def _open_tcp(self) -> socket.socket:
        per_addr_timeout = 12.0
        errors: list[str] = []
        try:
            infos = socket.getaddrinfo(
                self.server,
                self.port,
                type=socket.SOCK_STREAM,
                proto=socket.IPPROTO_TCP,
            )
        except OSError as exc:
            raise ConnectionError(f"DNS failed for {self.server}: {exc}") from exc
        for _family, _kind, _proto, _canon, sockaddr in infos:
            host = str(sockaddr[0])
            port = int(sockaddr[1])
            try:
                self.status(f"TCP connect {host}:{port}…")
                # Python 3.14+ may return 4-tuple sockaddrs (IPv6 flowinfo); create_connection wants (host, port).
                return socket.create_connection((host, port), timeout=per_addr_timeout)
            except OSError as exc:
                errors.append(f"{host}: {exc}")
        detail = "; ".join(errors[:4])
        if len(errors) > 4:
            detail += f" (+{len(errors) - 4} more)"
        raise ConnectionError(f"Could not reach {self.server}:{self.port} ({detail})")

    def connect(self) -> None:
        self.status(f"Connecting to {self.server}:{self.port}…")
        raw = self._open_tcp()
        if self.use_tls:
            ctx = ssl.create_default_context()
            self._sock = ctx.wrap_socket(raw, server_hostname=self.server)
        else:
            self._sock = raw
        # create_connection() leaves a default socket timeout; quiet channels (#bookz) then
        # hit recv timeout and look like an IRC drop while SearchBot is still working.
        self._sock.settimeout(None)
        self._send(f"NICK {self.nick}")
        self._send(f"USER bookpup 0 * :BookPup ebook portal")
        self._stop.clear()
        self._connected.clear()
        self._alive.set()
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline:
            if self._connected.is_set():
                break
            time.sleep(0.05)
        if not self._connected.is_set():
            self.close()
            raise ConnectionError(
                f"IRC registration timed out on {self.server} (no welcome from server)"
            )
        for ch in self.channels:
            self._presence.track_channel(ch)
            self._send(f"JOIN {ch}")
        self._channel_ready_at = time.monotonic() + IRC_POST_JOIN_COOLDOWN
        self.status(
            f"Connected as {self.nick} to {self.server} "
            f"(waiting {IRC_POST_JOIN_COOLDOWN}s after join)"
        )

    def _wait_post_join(self) -> None:
        delay = self._channel_ready_at - time.monotonic()
        if delay <= 0:
            return
        self.status(f"Post-join cooldown {delay:.1f}s…")
        time.sleep(delay)

    def switch_channel(self, channel: str) -> None:
        """Join another channel on the same server without reconnecting."""
        ch = (channel or "").strip()
        if not ch:
            return
        prev = self.channels[0] if self.channels else None
        self.channels = (ch,)
        self._discard_search_result_dcc()
        if self._sock and self.is_alive():
            if prev and prev.lower() != ch.lower():
                self._send(f"PART {prev}")
            self._presence.track_channel(ch)
            self._send(f"JOIN {ch}")
            self._channel_ready_at = time.monotonic() + IRC_POST_JOIN_COOLDOWN
            self.status(f"Switched to {ch}")

    def close(self) -> None:
        self._stop.set()
        if self._sock:
            try:
                self._send(f"QUIT :bye")
            except OSError:
                pass
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._alive.clear()

    def is_alive(self) -> bool:
        return bool(
            self._sock
            and not self._stop.is_set()
            and self._reader
            and self._reader.is_alive()
            and self._alive.is_set()
        )

    def reconnect(self, new_nick: bool = True) -> None:
        self.close()
        if new_nick:
            self.nick = random_nick()
        time.sleep(1)
        self.connect()

    def _send(self, line: str) -> None:
        if not self._sock:
            raise RuntimeError("not connected")
        self._sock.sendall((line + "\r\n").encode("utf-8", errors="replace"))

    def privmsg(self, target: str, text: str) -> None:
        irc_feed.append_out(target, text)  # uses worker thread-local owner when set
        self._send(f"PRIVMSG {target} :{text}")
        self.status(f"→ {target}: {text[:160]}")

    def _abort_search_wait(self, reason: str) -> None:
        self._search_abort_reason = reason[:300]
        self._search_aborted.set()
        with self._dcc_cond:
            self._dcc_cond.notify_all()

    def _abort_book_wait(self, reason: str) -> None:
        self._book_abort_reason = reason[:300]
        self._book_aborted.set()
        with self._dcc_cond:
            self._dcc_cond.notify_all()

    def _arm_book_dcc_wait(self) -> None:
        """Arm before outbound !get so fast bot NOTICEs are not missed."""
        with self._dcc_cond:
            self._awaiting_book_dcc = True
            self._book_aborted.clear()
            self._book_abort_reason = None

    def _disarm_book_dcc_wait(self) -> None:
        with self._dcc_cond:
            self._awaiting_book_dcc = False

    def _notice_to_us(self, line: str) -> bool:
        if " NOTICE " not in f" {line} ":
            return False
        m = _NOTICE_TARGET_RE.search(line)
        if not m:
            return False
        return _normalize_irc_target(m.group(1)) == self.nick.lower()

    def _privmsg_to_us(self, line: str) -> bool:
        if "PRIVMSG" not in line:
            return False
        m = _PRIVMSG_TARGET_RE.search(line)
        if not m:
            return False
        return _normalize_irc_target(m.group(1)) == self.nick.lower()

    def _maybe_abort_search(self, msg: str) -> None:
        text = (msg or "").strip()
        if not text or not is_search_no_matches_notice(text):
            return
        qnorm = None
        raw_q = extract_search_query_from_notice(text)
        if raw_q:
            qnorm = _norm_search_query(raw_q)
        with self._dcc_cond:
            if qnorm:
                self._no_match_queries.add(qnorm)
            wake = False
            if self._awaiting_search_dcc:
                if qnorm is None or qnorm == self._active_search_query:
                    wake = True
            if wake:
                self.status(f"Search empty: {text[:160]}")
                self._abort_search_wait(text)
            elif qnorm and raw_q:
                irc_feed.append_session(f"Search empty (noted for queue): {raw_q}")
        try:
            self.on_search_no_match(raw_q or "", text)
        except Exception as exc:
            irc_feed.append_session(f"Search no-match handler error: {exc}")

    def _maybe_abort_download(self, msg: str) -> None:
        text = (msg or "").strip()
        if not text or not is_fetch_abort_notice(text):
            return
        with self._dcc_cond:
            if not self._awaiting_book_dcc:
                return
            self.status(f"Download refused: {text[:160]}")
            self._abort_book_wait(text)

    def _discard_search_result_dcc(self) -> None:
        with self._dcc_cond:
            kept: list[DccOffer] = []
            for offer in self._pending_dcc:
                if is_search_results_dcc_filename(offer.filename):
                    self.status(f"Ignoring stale search DCC: {offer.filename}")
                else:
                    kept.append(offer)
            self._pending_dcc = kept

    def _take_dcc_offer(self, *, search_mode: bool) -> DccOffer | None:
        if not self._pending_dcc:
            return None
        if search_mode:
            return self._pending_dcc.pop(0)
        while self._pending_dcc:
            offer = self._pending_dcc.pop(0)
            if is_search_results_dcc_filename(offer.filename):
                self.status(f"Ignoring stale search DCC: {offer.filename}")
                continue
            return offer
        return None

    def _reply_ping(self, line: str) -> bool:
        stripped = line.strip()
        if stripped.startswith("PING "):
            self._send("PONG " + stripped[5:].strip())
            return True
        marker = " PING "
        idx = line.find(marker)
        if idx >= 0:
            self._send("PONG " + line[idx + len(marker) :].strip())
            return True
        return False

    def _extend_book_offer_deadline(self) -> None:
        with self._dcc_cond:
            cap = time.monotonic() + BOOK_OFFER_MAX_SECONDS
            extended = min(self._book_offer_deadline + BOOK_OFFER_EXTEND_SECONDS, cap)
            self._book_offer_deadline = max(self._book_offer_deadline, extended)
            self._dcc_cond.notify_all()

    def _maybe_extend_book_wait(self, line: str, msg: str) -> None:
        if not self._awaiting_book_dcc or not self._active_book_bot:
            return
        if not (self._notice_to_us(line) or self._privmsg_to_us(line)):
            return
        sender = irc_prefix_nick(line)
        if not sender or sender != self._active_book_bot:
            return
        text = (msg or "").strip()
        if not text or is_download_failure_notice(text):
            return
        if BOOK_ACTIVITY_RE.search(text):
            self._extend_book_offer_deadline()

    def wait_dcc(self, timeout: float, *, search_mode: bool = False) -> DccOffer:
        if search_mode:
            deadline = time.monotonic() + timeout
        else:
            with self._dcc_cond:
                self._book_offer_deadline = time.monotonic() + timeout
        with self._dcc_cond:
            if search_mode:
                self._awaiting_search_dcc = True
            else:
                self._awaiting_book_dcc = True
                self._book_aborted.clear()
                self._book_abort_reason = None
            try:
                while True:
                    if search_mode and self._search_aborted.is_set():
                        raise SearchNoMatchesError(
                            self._search_abort_reason or "Search returned no matches"
                        )
                    if not search_mode and self._book_aborted.is_set():
                        raise DownloadRequestError(
                            self._book_abort_reason or "Download refused by IRC bots"
                        )
                    offer = self._take_dcc_offer(search_mode=search_mode)
                    if offer is not None:
                        return offer
                    if not self.is_alive():
                        raise ConnectionError(self.last_error or "IRC disconnected")
                    deadline = (
                        time.monotonic() + timeout
                        if search_mode
                        else self._book_offer_deadline
                    )
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        if search_mode:
                            raise TimeoutError("DCC offer timed out")
                        bot = self._active_book_bot or "bot"
                        secs = int(timeout)
                        raise DownloadRequestError(
                            f"No DCC from {bot} within {secs}s — bot may be offline "
                            f"or ignoring this trigger."
                        )
                    self._dcc_cond.wait(timeout=min(remaining, 2.0))
            finally:
                if search_mode:
                    self._awaiting_search_dcc = False
                else:
                    self._awaiting_book_dcc = False
                    self._book_offer_deadline = 0.0

    def preflight_fetch(
        self,
        channel: str,
        bot_nick: str | None,
        *,
        check_presence: bool = True,
    ) -> None:
        from .core import IRC_MOCK

        if IRC_MOCK or not bot_nick:
            return
        ch = normalize_channel(channel)
        if check_presence:
            ready = self._presence.wait_names_ready(ch, 5.0)
            if not ready:
                self.status("Channel NAMES incomplete; using best-effort presence check")
            if not self._presence.is_in_channel(ch, bot_nick):
                raise DownloadRequestError(
                    f"Bot {bot_nick} not in {ch} (likely offline). "
                    "Try another row or network."
                )
        if self._health.is_stale(bot_nick):
            raise DownloadRequestError(
                f"Bot {bot_nick} hasn't been seen recently in {ch}; it may be offline."
            )
        warn = self._health.warn_full_slots(bot_nick)
        if warn:
            self.status(warn)

    def receive_dcc_file(self, offer: DccOffer, dest_path: str, timeout: float) -> None:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                self._receive_dcc_once(offer, dest_path, timeout)
                return
            except (ConnectionResetError, ConnectionError, OSError) as exc:
                last_err = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        if last_err:
            raise last_err

    def _receive_dcc_once(self, offer: DccOffer, dest_path: str, timeout: float) -> None:
        sock = socket.create_connection((offer.host, offer.port), timeout=30)
        sock.settimeout(timeout)
        received = 0
        bufsize = 1024
        try:
            with open(dest_path, "wb") as fh:
                while received < offer.size:
                    chunk = sock.recv(min(bufsize, offer.size - received))
                    if not chunk:
                        raise ConnectionError("DCC truncated")
                    fh.write(chunk)
                    received += len(chunk)
                    sock.sendall(struct.pack(">I", received))
        finally:
            sock.close()
        if received < offer.size:
            raise ConnectionError("DCC incomplete")

    def search_and_download_results(
        self, channel: str, query: str, dest_zip: str
    ) -> None:
        qnorm = _norm_search_query(query)
        with self._dcc_cond:
            if qnorm in self._no_match_queries:
                self._no_match_queries.discard(qnorm)
                raise SearchNoMatchesError(
                    f'Search returned no matches for "{query.strip()}"'
                )
            self._active_search_query = qnorm
            self._search_aborted.clear()
            self._search_abort_reason = None
        try:
            self._wait_post_join()
            self.privmsg(channel, f"@search {query}")
            self.status("Waiting for search results (DCC)…")
            offer = self.wait_dcc(SEARCH_TIMEOUT, search_mode=True)
            self.status(
                f"Receiving {offer.filename} ({offer.size // 1024} KB via DCC)…"
            )
            self.receive_dcc_file(offer, dest_zip, SEARCH_TIMEOUT)
            self.status("Search results received")
            self._discard_search_result_dcc()
        finally:
            with self._dcc_cond:
                self._active_search_query = None

    def request_book(self, channel: str, command_line: str, dest_path: str) -> DccOffer:
        self._wait_post_join()
        bot = serving_bot_nick(command_line)
        self._active_book_bot = bot
        self.preflight_fetch(channel, bot, check_presence=True)
        self._discard_search_result_dcc()
        self._arm_book_dcc_wait()
        offer_timeout = download_offer_timeout()
        try:
            self.privmsg(channel, command_line)
            self.status("Waiting for book file (DCC)…")
            offer = self.wait_dcc(offer_timeout, search_mode=False)
            self.status(f"Downloading {offer.filename} ({offer.size // 1024} KB)…")
            self.receive_dcc_file(offer, dest_path, DOWNLOAD_TIMEOUT)
            self.status(f"Downloaded {offer.filename}")
            return offer
        finally:
            self._active_book_bot = None
            self._disarm_book_dcc_wait()

    def request_xdcc(self, botnick: str, slot: int, dest_path: str) -> DccOffer:
        self._wait_post_join()
        self._discard_search_result_dcc()
        nick = (botnick or "").strip()
        if not nick:
            raise DownloadRequestError("Missing XDCC bot name")
        if slot < 1:
            raise DownloadRequestError("Invalid XDCC slot")
        text = f"xdcc send #{slot}"
        self._active_book_bot = nick.lower()
        self.preflight_fetch(channel="", bot=nick, check_presence=False)
        self._arm_book_dcc_wait()
        offer_timeout = download_offer_timeout()
        try:
            self.privmsg(nick, text)
            self.status(f"Waiting for XDCC from {nick} (#{slot})…")
            offer = self.wait_dcc(offer_timeout, search_mode=False)
            self.status(f"Downloading {offer.filename} ({offer.size // 1024} KB)…")
            self.receive_dcc_file(offer, dest_path, DOWNLOAD_TIMEOUT)
            self.status(f"Downloaded {offer.filename}")
            return offer
        finally:
            self._active_book_bot = None
            self._disarm_book_dcc_wait()

    def _read_loop(self) -> None:
        assert self._sock
        buf = b""
        while not self._stop.is_set():
            try:
                data = self._sock.recv(4096)
            except OSError:
                break
            if not data:
                break
            buf += data
            while b"\r\n" in buf:
                line, buf = buf.split(b"\r\n", 1)
                try:
                    text = line.decode("utf-8", errors="replace")
                except UnicodeDecodeError:
                    continue
                self._handle_line(text)
        self._alive.clear()
        with self._dcc_cond:
            self._dcc_cond.notify_all()
        self.last_error = self.last_error or "IRC disconnected"
        irc_feed.append_session(self.last_error, owner=self.feed_owner)

    def _handle_line(self, line: str) -> None:
        if self._reply_ping(line):
            return
        if " ERROR " in f" {line} ":
            self.last_error = line.strip()[:240]
            irc_feed.append_session(f"IRC ERROR: {self.last_error}", owner=self.feed_owner)
            return
        if "PRIVMSG" in line or "NOTICE" in line or " JOIN " in line:
            irc_feed.append_in_line(line, owner=self.feed_owner)
        elif "DCC SEND" in line.upper():
            irc_feed.append_in_line(line, owner=self.feed_owner)
        if " 001 " in line or " 376 " in line or " 422 " in line:
            self._connected.set()
        if " 433 " in line:
            self.last_error = "nickname in use"
        self._presence.handle_server_line(line)
        if "PRIVMSG" in line:
            msg = irc_trailing_message(line)
            m = _PRIVMSG_TARGET_RE.search(line)
            if m and self._presence.is_tracked_channel(m.group(1)):
                self._health.ingest_channel_message(msg)
        if "PRIVMSG" in line or " NOTICE " in f" {line} ":
            self._maybe_dcc(line)
            msg = irc_trailing_message(line)
            self._maybe_extend_book_wait(line, msg)
            if self._notice_to_us(line):
                self._maybe_abort_search(msg)
                self._maybe_abort_download(msg)
            elif self._privmsg_to_us(line):
                self._maybe_abort_download(msg)
            if " NOTICE " in f" {line} ":
                self.on_notice(msg)
                if self.on_status and self._notice_to_us(line) and msg:
                    self.status(f"Notice: {msg[:200]}")

    def _maybe_dcc(self, line: str) -> None:
        payload = None
        if "\x01" in line:
            for part in line.split("\x01"):
                if part.upper().startswith("DCC SEND"):
                    payload = part
                    break
        if not payload and "DCC SEND" in line.upper():
            idx = line.upper().find("DCC SEND")
            payload = line[idx:]
        if not payload:
            return
        offer = _parse_dcc_payload(payload)
        if not offer:
            return
        self.status(
            f"DCC offer: {offer.filename} ({offer.host}:{offer.port}, {offer.size} bytes)"
        )
        with self._dcc_cond:
            self._pending_dcc.append(offer)
            self._dcc_cond.notify_all()