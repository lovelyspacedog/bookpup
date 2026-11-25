"""Serial IRC job queue (one operation at a time)."""

from __future__ import annotations

import shutil
import threading
import time
import zipfile
from pathlib import Path
from queue import Empty, Queue

from . import irc_feed
from . import core
from .core import IRC_IDLE_DISCONNECT_SECONDS, ensure_dirs
from . import jobs
from . import library
from . import quota
from . import user_paths
from .core import MAX_DCC_RECEIVE_BYTES, MAX_DCC_SEARCH_BYTES
from .irc_client import (
    DownloadRequestError,
    IrcSession,
    SearchNoMatchesError,
    random_nick,
)
from .irc_session_target import SessionTarget, target_for_job
from .irc_targets import (
    is_search_all,
    is_soulseek_search,
    is_xdcc_search,
    resolve_target,
    search_target_ids,
)
from . import gutenberg_fetch
from .search_results import parse_results_text, parse_results_zip
from .staging import create_staging
from . import soulseek_search
from . import soulseek_fetch
from . import xdcc_search
from .xdcc_search import XdccSearchDisabledError, XdccSearchError


def _dcc_byte_cap_for_job(job: dict) -> int:
    owner = str(job.get("owner") or "").strip()
    cap = MAX_DCC_RECEIVE_BYTES
    if owner:
        rem = int(quota.library_usage_for(owner).get("remaining_bytes") or 0)
        cap = min(cap, max(rem, 0))
    return cap


class IrcWorker:
    def __init__(self) -> None:
        self._q: Queue[str] = Queue()
        self._xdcc_q: Queue[str] = Queue()
        self._thread: threading.Thread | None = None
        self._session: IrcSession | None = None
        self._lock = threading.Lock()
        self._current_job_id: str | None = None
        self._idle_since: float | None = None
        self._session_binding: tuple[str, int, bool, str] | None = None

    def start(self) -> None:
        ensure_dirs()
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._loop, name="bookpup-irc", daemon=True)
        self._thread.start()

    def enqueue(self, job_id: str) -> None:
        try:
            job = jobs.load_job(job_id)
            if job.get("state") == "queued":
                jobs.set_irc_status(job_id, "Queued for IRC…")
        except KeyError:
            pass
        self._q.put(job_id)
        self.start()

    def enqueue_xdcc_search(self, job_id: str) -> None:
        """HTTP-only XDCC index sniff — bypasses IRC download queue."""
        self._xdcc_q.put(job_id)
        self.start()

    def health_snapshot(self) -> dict[str, bool]:
        with self._lock:
            alive = self._thread is not None and self._thread.is_alive()
            connected = self._session is not None and self._session.is_alive()
        return {
            "irc_worker_alive": alive,
            "irc_connected": connected,
        }

    def disconnect_now(self, *, owner: str | None = None) -> bool:
        """Close the live IRC session when the queue is idle (manual disconnect)."""
        if self._has_active_queue_work():
            raise ValueError(
                "IRC is busy with a sniff or fetch — wait or call off the job first"
            )
        with self._lock:
            had = bool(self._session and self._session.is_alive())
            if self._session:
                self._session.close()
            self._session = None
            self._session_binding = None
            self._idle_since = None
        if had:
            irc_feed.append_session("IRC disconnected (manual)", owner=owner)
        return had

    def interrupt(self, job_id: str) -> None:
        """Break an in-flight IRC/DCC wait for a cancelled job."""
        with self._lock:
            if self._current_job_id != job_id:
                return
            if self._session:
                self._session.close()
            self._session = None
            self._session_binding = None

    def _has_active_queue_work(self) -> bool:
        if self._current_job_id:
            return True
        try:
            if self._q.qsize() > 0:
                return True
        except NotImplementedError:
            pass
        return jobs.queue_has_active_work()

    def _maybe_idle_disconnect(self) -> None:
        if core.IRC_MOCK:
            return
        if self._has_active_queue_work():
            self._idle_since = None
            return
        now = time.monotonic()
        if self._idle_since is None:
            self._idle_since = now
            return
        if now - self._idle_since < IRC_IDLE_DISCONNECT_SECONDS:
            return
        with self._lock:
            if self._session and self._session.is_alive():
                irc_feed.append_session(
                    f"Queue idle {IRC_IDLE_DISCONNECT_SECONDS // 60}m — disconnecting IRC"
                )
                self._session.close()
                self._session = None
                self._session_binding = None
        self._idle_since = None

    def _loop(self) -> None:
        while True:
            job_id: str | None = None
            from_main_q = False
            try:
                job_id = self._xdcc_q.get_nowait()
            except Empty:
                pass
            if job_id is None:
                try:
                    job_id = self._q.get(timeout=2.0)
                    from_main_q = True
                except Empty:
                    self._maybe_idle_disconnect()
                    continue
            self._idle_since = None
            try:
                self._run_job(job_id)
            except Exception as exc:
                missing = isinstance(exc, KeyError) and job_id and exc.args == (job_id,)
                if not missing:
                    try:
                        job = jobs.load_job(job_id)
                        if job.get("state") == "cancelled":
                            pass
                        else:
                            job["state"] = "error"
                            job["error"] = str(exc)
                            jobs.save_job(job)
                    except KeyError:
                        pass
                    irc_feed.append_session(f"Worker job error: {exc}")
            finally:
                if from_main_q:
                    self._q.task_done()

    def _job_target(self, job: dict) -> SessionTarget:
        return target_for_job(job)

    def send_chat(self, owner: str, channel: str, message: str) -> None:
        text = " ".join(str(message or "").replace("\r", " ").replace("\n", " ").split())
        if not text:
            raise ValueError("Message required")
        if len(text) > 400:
            raise ValueError("Message too long (max 400 characters)")
        if text.startswith("!"):
            raise ValueError("Chat cannot start with ! (use Search for downloads)")
        target = resolve_target(channel)
        ch = target.channel
        if not ch:
            raise ValueError("Choose an IRC channel for chat (not XDCC index)")
        session_target = SessionTarget(
            id=target.id,
            network=target.network,
            channel=target.channel,
            server=target.server,
            port=target.port,
            use_tls=target.use_tls,
        )
        self.start()
        if core.IRC_MOCK:
            irc_feed.set_job_owner(owner)
            try:
                irc_feed.append_out(ch, text)
            finally:
                irc_feed.set_job_owner(None)
            return
        with self._lock:
            session = self._ensure_session(session_target, feed_owner=owner)
            irc_feed.set_job_owner(owner)
            try:
                session.privmsg(ch, text)
            finally:
                irc_feed.set_job_owner(None)
        self._idle_since = None

    def _on_search_no_match(self, query: str, reason: str) -> None:
        ids: list[str] = []
        if query.strip():
            ids = jobs.complete_search_no_matches(query, reason)
        if not ids and self._current_job_id:
            try:
                job = jobs.load_job(self._current_job_id)
            except KeyError:
                job = None
            if (
                job
                and job.get("type") == "search"
                and job.get("state") in ("queued", "running")
            ):
                q = str(job.get("query") or "").strip()
                if q:
                    ids = jobs.complete_search_no_matches(q, reason)
        if ids:
            irc_feed.append_session(
                f"Search jobs completed (no matches): {(query or ids[0])[:80]} ({len(ids)})"
            )
        with self._lock:
            if self._current_job_id and self._current_job_id in ids and self._session:
                self._session._abort_search_wait(reason)

    def _bind_session_status(self, job_id: str) -> None:
        with self._lock:
            if self._session:
                self._session.on_status = lambda msg: jobs.set_irc_status(job_id, msg)

    def _clear_session_status(self) -> None:
        with self._lock:
            if self._session:
                self._session.on_status = None

    def _binding_for(self, target: SessionTarget) -> tuple[str, int, bool, str]:
        return target.binding()

    def _ensure_session(
        self,
        target: SessionTarget,
        *,
        feed_owner: str | None = None,
        job_id: str | None = None,
    ) -> IrcSession:
        binding = self._binding_for(target)
        with self._lock:
            # Fresh TCP per channel on same server (IRCHighway #bookz dropped on PART/switch).
            need_new = (
                self._session is None
                or not self._session.is_alive()
                or self._session_binding != binding
            )
            if need_new:
                if self._session:
                    self._session.close()
                self._session = None
                self._session_binding = None
            else:
                self._session.on_search_no_match = self._on_search_no_match
                if feed_owner:
                    self._session.feed_owner = feed_owner
                return self._session
        session = IrcSession(
            target.server,
            target.port,
            use_tls=target.use_tls,
            channels=(target.channel,),
            nick=random_nick(),
            on_search_no_match=self._on_search_no_match,
        )
        if job_id:
            session.on_status = lambda msg: jobs.set_irc_status(job_id, msg)
        try:
            session.connect()
        except Exception:
            session.close()
            raise
        if feed_owner:
            session.feed_owner = feed_owner
        with self._lock:
            self._session = session
            self._session_binding = binding
            return self._session

    def _reset_session(self) -> None:
        with self._lock:
            if self._session:
                self._session.close()
            self._session = None
            self._session_binding = None

    def _run_job(self, job_id: str) -> None:
        try:
            job = jobs.load_job(job_id)
        except KeyError:
            return
        if job.get("state") in ("cancelled", "done"):
            return
        self._current_job_id = job_id
        owner = str(job.get("owner") or "").strip() or None
        if owner:
            user_paths.set_user(owner)
        irc_feed.set_job_owner(owner)
        try:
            job["state"] = "running"
            jobs.set_irc_status(job_id, f"Starting {job.get('type', 'job')}…")
            jobs.save_job(job)
            attempts = 0
            while attempts < 3:
                job = jobs.load_job(job_id)
                if job.get("state") == "cancelled":
                    return
                try:
                    if core.IRC_MOCK:
                        irc_feed.append_session("Running in IRC mock mode")
                        self._run_mock(job)
                    else:
                        self._run_live(job)
                    job = jobs.load_job(job_id)
                    if job.get("type") == "download" and not job.get("library_item_id"):
                        item = library.auto_stash_from_job(job)
                        if item and item.get("id"):
                            job["library_item_id"] = item["id"]
                            jobs.save_job(job)
                    completed = jobs.complete_job_success(job_id)
                    if completed is None:
                        return
                    from . import notify

                    notify.maybe_job_done(completed)
                    return
                except DownloadRequestError as exc:
                    job = jobs.load_job(job_id)
                    if job.get("state") == "cancelled":
                        return
                    job["state"] = "error"
                    job["error"] = str(exc)[:400]
                    job.pop("irc_status", None)
                    job.pop("irc_status_at", None)
                    jobs.save_job(job)
                    irc_feed.append_session(f"Download refused: {exc}")
                    return
                except Exception as exc:
                    job = jobs.load_job(job_id)
                    if job.get("state") == "cancelled":
                        return
                    if job.get("type") == "search" and is_search_all(job.get("channel")):
                        if job.get("results"):
                            job["state"] = "done"
                            job.pop("error", None)
                            job.pop("irc_status", None)
                            job.pop("irc_status_at", None)
                            note = str(exc)[:200]
                            if note:
                                job["search_notice"] = note
                            jobs.save_job(job)
                            irc_feed.append_session(
                                f"Search all stopped early ({len(job.get('results') or [])} rows kept)"
                            )
                            return
                    attempts += 1
                    job["error"] = str(exc)
                    jobs.save_job(job)
                    irc_feed.append_session(f"Job error: {exc}")
                    self._reset_session()
                    time.sleep(1)
            job = jobs.load_job(job_id)
            if job.get("state") == "cancelled":
                return
            job["state"] = "error"
            job.pop("irc_status", None)
            job.pop("irc_status_at", None)
            jobs.save_job(job)
        finally:
            irc_feed.set_job_owner(None)
            user_paths.set_user(None)
            self._clear_session_status()
            if self._current_job_id == job_id:
                self._current_job_id = None

    def _run_search_all(self, job: dict, job_id: str) -> None:
        query = str(job.get("query") or "").strip()
        owner = str(job.get("owner") or "").strip() or None
        staging_id = job["id"]
        merged: list[dict] = []
        notices: list[str] = []
        targets = search_target_ids()
        total_steps = len(targets)
        create_staging(staging_id)
        for idx, tid in enumerate(targets, start=1):
            job = jobs.load_job(job_id)
            if job.get("state") == "cancelled":
                return
            target = resolve_target(tid)
            session_target = SessionTarget(
                id=target.id,
                network=target.network,
                channel=target.channel,
                server=target.server,
                port=target.port,
                use_tls=target.use_tls,
            )
            jobs.set_irc_status(
                job_id,
                f"Sniff {idx}/{total_steps}: {target.display}…",
            )
            session = self._ensure_session(session_target, feed_owner=owner, job_id=job_id)
            self._bind_session_status(job_id)
            zip_path = str(create_staging(staging_id) / f"results-{idx}.zip")
            job["awaiting_irc_search"] = True
            jobs.save_job(job)
            try:
                session.search_and_download_results(target.channel, query, zip_path)
                rows = parse_results_zip(zip_path)
                for row in rows:
                    entry = row.to_dict()
                    entry["irc_target"] = tid
                    entry["network"] = target.network
                    merged.append(entry)
            except SearchNoMatchesError as exc:
                notices.append(f"{target.network}: no matches")
                irc_feed.append_session(f"{target.display}: {exc}")
            except Exception as exc:
                notices.append(f"{target.network}: {exc}")
                irc_feed.append_session(f"{target.display} failed: {exc}")
                self._reset_session()
            finally:
                if self._session:
                    self._session._discard_search_result_dcc()
                job = jobs.load_job(job_id)
                job.pop("awaiting_irc_search", None)
                job["results"] = merged
                job["result_count"] = len(merged)
                job["staging_id"] = staging_id
                jobs.save_job(job)
        job = jobs.load_job(job_id)
        if job.get("state") == "cancelled":
            return
        job["results"] = merged
        job["result_count"] = len(merged)
        if not merged and notices:
            job["search_notice"] = "; ".join(notices)[:240]
        elif notices:
            job["search_notices"] = notices
        job.pop("awaiting_irc_search", None)
        jobs.save_job(job)

    def _run_xdcc_search(self, job: dict, job_id: str) -> None:
        owner = str(job.get("owner") or "").strip() or None
        xdcc_search.run_search_job(job, owner=owner)

    def _run_live(self, job: dict) -> None:
        job_id = str(job["id"])
        if job["type"] == "search" and is_search_all(job.get("channel")):
            self._run_search_all(job, job_id)
            return
        if job["type"] == "search" and is_xdcc_search(job.get("channel")):
            self._run_xdcc_search(job, job_id)
            return
        if job["type"] == "search" and is_soulseek_search(job.get("channel")):
            owner = str(job.get("owner") or "").strip() or None
            soulseek_search.run_search_job(job, owner=owner)
            return
        if job["type"] == "download" and str(job.get("download_kind") or "").lower() == "soulseek":
            soulseek_fetch.run_download_job(job)
            return
        target = self._job_target(job)
        if not target.server:
            raise ValueError("No IRC server for job")
        owner = str(job.get("owner") or "").strip() or None
        jobs.set_irc_status(job_id, f"Connecting to {target.network}…")
        session = self._ensure_session(target, feed_owner=owner, job_id=job_id)
        self._bind_session_status(job_id)
        jobs.set_irc_status(job_id, f"IRC ready on {target.display} ({session.nick})")
        channel = target.channel
        if job["type"] == "search":
            job = jobs.load_job(str(job["id"]))
            if job.get("state") == "done":
                return
            staging_id = job["id"]
            zip_path = str(create_staging(staging_id) / "results.zip")
            job["awaiting_irc_search"] = True
            jobs.save_job(job)
            jobs.set_irc_status(job_id, f"@search on {target.display}")
            try:
                session.search_and_download_results(
                    channel,
                    str(job["query"]),
                    zip_path,
                    max_bytes=MAX_DCC_SEARCH_BYTES,
                )
                jobs.set_irc_status(job_id, "Parsing search results…")
                rows = parse_results_zip(zip_path)
                jobs.set_irc_status(job_id, f"Parsed {len(rows)} match(es)")
            except SearchNoMatchesError as exc:
                job = jobs.load_job(staging_id)
                if job.get("state") != "done":
                    job["results"] = []
                    job["result_count"] = 0
                    job["staging_id"] = staging_id
                    job["search_notice"] = str(exc)[:240]
                    job.pop("awaiting_irc_search", None)
                    jobs.save_job(job)
                return
            job = jobs.load_job(staging_id)
            job["results"] = [r.to_dict() for r in rows]
            job["result_count"] = len(rows)
            job["staging_id"] = staging_id
            for entry in job["results"]:
                entry.setdefault("irc_target", target.id)
                entry.setdefault("network", target.network)
            job.pop("awaiting_irc_search", None)
            jobs.save_job(job)
            irc_feed.append_session(
                f"Sniff finished: {len(rows)} row(s) for {job.get('query', '')!r}"
            )
        elif job["type"] == "download":
            staging_id = job.get("staging_id") or job["id"]
            create_staging(staging_id)
            dest = create_staging(staging_id) / "raw"
            xdcc = job.get("xdcc")
            if isinstance(xdcc, dict) and job.get("download_kind") == "xdcc":
                xdcc = xdcc_search.ensure_xdcc_server(xdcc)
                job["xdcc"] = xdcc
                jobs.save_job(job)
                bot = str(xdcc.get("botname") or "").strip()
                slot = int(xdcc.get("slot") or 0)
                jobs.set_irc_status(job_id, f"XDCC fetch from {bot} on {target.display}")
                irc_feed.append_out(bot, f"xdcc send #{slot}")
                offer = session.request_xdcc(
                    bot, slot, str(dest), max_bytes=_dcc_byte_cap_for_job(job)
                )
            else:
                jobs.set_irc_status(job_id, f"Requesting book on {target.display}")
                irc_cmd = str(job.get("command") or "")
                hint = job.get("command_rewrite_hint")
                if hint:
                    irc_feed.append_session(str(hint))
                try:
                    offer = session.request_book(
                        channel, irc_cmd, str(dest), max_bytes=_dcc_byte_cap_for_job(job)
                    )
                except DownloadRequestError as exc:
                    fb = gutenberg_fetch.gutenberg_fallback_after_irc_refusal(
                        reason=str(exc),
                        command=irc_cmd,
                        title=str(job.get("title") or "") or None,
                        dest_path=dest,
                        on_status=lambda m: jobs.set_irc_status(job_id, m),
                    )
                    if fb is None:
                        raise
                    irc_feed.append_session(fb.feed)
                    job["gutenberg_fallback"] = True
                    offer = fb.offer
            final = dest
            safe_name = offer.filename.replace('"', "").strip()
            if safe_name and "." in safe_name:
                final = dest.parent / f"raw{Path(safe_name).suffix}"
                if final.exists():
                    final.unlink()
                shutil.move(dest, final)
            job["staging_id"] = staging_id
            job["raw_name"] = final.name
            job["raw_bytes"] = final.stat().st_size
            jobs.save_job(job)
        else:
            raise ValueError(f"unknown job type {job['type']}")

    def _run_mock(self, job: dict) -> None:
        fixture = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "sample_results.txt"
        target = self._job_target(job)
        channel = target.channel
        if job["type"] == "search":
            if is_search_all(job.get("channel")):
                merged: list[dict] = []
                for tid in search_target_ids():
                    t = resolve_target(tid)
                    rows = parse_results_text(fixture.read_text())
                    for row in rows:
                        entry = row.to_dict()
                        entry["irc_target"] = tid
                        entry["network"] = t.network
                        merged.append(entry)
                job["results"] = merged
                job["result_count"] = len(merged)
                job["staging_id"] = job["id"]
                create_staging(job["id"])
                jobs.save_job(job)
            elif is_xdcc_search(job.get("channel")):
                rows = xdcc_search.search(str(job.get("query") or ""))
                job["results"] = rows
                job["result_count"] = len(rows)
                job["staging_id"] = job["id"]
                create_staging(job["id"])
                jobs.save_job(job)
            elif is_soulseek_search(job.get("channel")):
                rows = soulseek_search.search_remote(str(job.get("query") or ""))
                job["results"] = rows
                job["result_count"] = len(rows)
                job["staging_id"] = job["id"]
                create_staging(job["id"])
                jobs.save_job(job)
            else:
                irc_feed.append_out(channel, f"@search {job.get('query', '')}")
                staging_id = job["id"]
                create_staging(staging_id)
                zip_path = create_staging(staging_id) / "results.zip"
                with zipfile.ZipFile(zip_path, "w") as zf:
                    zf.writestr("results.txt", fixture.read_text())
                rows = parse_results_zip(zip_path)
                job["results"] = [r.to_dict() for r in rows]
                job["result_count"] = len(rows)
                job["staging_id"] = staging_id
                for entry in job["results"]:
                    entry.setdefault("irc_target", target.id)
                    entry.setdefault("network", target.network)
                jobs.save_job(job)
        elif job["type"] == "download":
            if str(job.get("download_kind") or "").lower() == "soulseek":
                sk = job.get("soulseek") if isinstance(job.get("soulseek"), dict) else {}
                user = str(sk.get("username") or "peer")
                irc_feed.append_out(user, f'soulseek fetch "{sk.get("filename", "")[:80]}"')
                staging_id = job.get("staging_id") or job["id"]
                base = create_staging(staging_id)
                title = str(job.get("title") or "mock.epub")
                ext = Path(title).suffix or ".epub"
                raw = base / f"raw{ext}"
                raw.write_bytes(b"MOCK-SOULSEEK")
                job["staging_id"] = staging_id
                job["raw_name"] = raw.name
                job["raw_bytes"] = raw.stat().st_size
                jobs.save_job(job)
                return
            xdcc = job.get("xdcc")
            if isinstance(xdcc, dict) and job.get("download_kind") == "xdcc":
                bot = str(xdcc.get("botname") or "bot")
                slot = int(xdcc.get("slot") or 1)
                irc_feed.append_out(bot, f"xdcc send #{slot}")
            else:
                irc_feed.append_out(channel, str(job.get("command", "")))
            staging_id = job.get("staging_id") or job["id"]
            base = create_staging(staging_id)
            ext = ".cbz" if job.get("download_kind") == "xdcc" else ".epub"
            raw = base / f"raw{ext}"
            raw.write_bytes(b"MOCK-XDCC" if ext == ".cbz" else b"MOCK-EPUB")
            job["staging_id"] = staging_id
            job["raw_name"] = raw.name
            job["raw_bytes"] = raw.stat().st_size
            jobs.save_job(job)


worker = IrcWorker()