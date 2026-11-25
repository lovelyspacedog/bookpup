"""In-process scheduled refresh of Dig popular list from dig_bestsellers_url."""

from __future__ import annotations

import threading
import time

from . import dig_bestsellers_refresh
from .core import load_config

_runner: "DigBestsellersRunner | None" = None

TICK_SECONDS = 300.0


def _tick_seconds() -> float:
    try:
        return max(60.0, float(load_config().get("dig_bestsellers_tick_seconds") or TICK_SECONDS))
    except (TypeError, ValueError):
        return TICK_SECONDS


class DigBestsellersRunner:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._busy = threading.Lock()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="bookpup-dig-bestsellers", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        self._stop.wait(15.0)
        while not self._stop.is_set():
            try:
                self._tick_once()
            except Exception:
                pass
            self._stop.wait(_tick_seconds())

    def _tick_once(self) -> None:
        if not dig_bestsellers_refresh.due_for_refresh():
            return
        if not self._busy.acquire(blocking=False):
            return
        try:
            dig_bestsellers_refresh.fetch_and_store_bestsellers()
        except Exception as exc:
            dig_bestsellers_refresh.record_refresh_failure(str(exc))
        finally:
            self._busy.release()


def start_dig_bestsellers_scheduler() -> None:
    global _runner
    if _runner is None:
        _runner = DigBestsellersRunner()
    _runner.start()