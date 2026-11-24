"""In-process scheduled re-sniffs for bookmark watches."""

from __future__ import annotations

import threading
import time
from typing import Any

from . import jobs, notify, search_run, search_workspace
from .search_workspace import MAX_SEEN_KEYS
from . import core
from .core import load_config
from .search_run import SearchStartError

_runner: "ScheduleRunner | None" = None


def tick_seconds() -> float:
    cfg = core._config if core._config is not None else None
    if cfg is None and core.CONFIG_FILE.is_file():
        try:
            cfg = load_config()
        except OSError:
            cfg = None
    if not isinstance(cfg, dict):
        return 60.0
    try:
        return max(15.0, float(cfg.get("sniff_schedule_tick_seconds") or 60))
    except (TypeError, ValueError):
        return 60.0


class ScheduleRunner:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="bookpup-sniff-schedule", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick_once()
            except Exception:
                pass
            self._stop.wait(tick_seconds())

    def _tick_once(self) -> None:
        if jobs.queue_has_active_work():
            return
        due = search_workspace.list_due_watches()
        if not due:
            return
        for watch in due:
            if jobs.queue_has_active_work():
                return
            self._run_watch(watch)

    def _run_watch(self, watch: dict[str, Any]) -> None:
        username = str(watch["username"])
        saved_id = str(watch["saved_id"])
        if not self._lock.acquire(blocking=False):
            return
        try:
            search_workspace.patch_saved_schedule(
                username,
                saved_id,
                {"running": True, "last_error": ""},
            )
            job = search_run.run_search_job_for_user(
                username,
                watch["query"],
                watch["channel"],
                wait=True,
            )
            state = str(job.get("state") or "")
            if state != "done":
                err = str(job.get("error") or "Sniff failed")
                search_workspace.patch_saved_schedule(
                    username,
                    saved_id,
                    {
                        "running": False,
                        "last_run_at": time.time(),
                        "last_error": err[:240],
                    },
                )
                return
            results = job.get("results")
            if not isinstance(results, list):
                results = []
            sched = watch.get("schedule") if isinstance(watch.get("schedule"), dict) else {}
            seen = list(sched.get("seen_keys") or [])
            new_rows, new_keys = search_workspace.diff_new_rows(results, seen)
            merged = seen + new_keys
            if len(merged) > MAX_SEEN_KEYS:
                merged = merged[-MAX_SEEN_KEYS:]
            now = time.time()
            patch: dict[str, Any] = {
                "running": False,
                "last_run_at": now,
                "seen_keys": merged,
                "last_error": "",
            }
            search_workspace.patch_saved_schedule(username, saved_id, patch)
            if new_rows:
                notify.sniff_watch_pm(
                    owner=username,
                    watch_name=str(watch.get("name") or "bookmark"),
                    query=str(watch.get("query") or ""),
                    new_rows=new_rows,
                )
                search_workspace.patch_saved_schedule(
                    username,
                    saved_id,
                    {"last_notify_at": now},
                )
        except SearchStartError as exc:
            search_workspace.patch_saved_schedule(
                username,
                saved_id,
                {
                    "running": False,
                    "last_run_at": time.time(),
                    "last_error": str(exc)[:240],
                },
            )
        except KeyError:
            pass
        except Exception as exc:
            search_workspace.patch_saved_schedule(
                username,
                saved_id,
                {
                    "running": False,
                    "last_run_at": time.time(),
                    "last_error": str(exc)[:240],
                },
            )
        finally:
            self._lock.release()


def start_scheduler() -> None:
    global _runner
    search_workspace.recover_stale_running_schedules()
    if _runner is None:
        _runner = ScheduleRunner()
    _runner.start()