"""Concurrency cap for public sideload downloads (per client IP)."""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator

from .client_ip import client_key

MAX_CONCURRENT_PER_IP = 3
_guard = threading.Lock()
_sems: dict[str, threading.BoundedSemaphore] = {}


def _sem_for(ip: str) -> threading.BoundedSemaphore:
    key = str(ip or "unknown").strip() or "unknown"
    with _guard:
        sem = _sems.get(key)
        if sem is None:
            sem = threading.BoundedSemaphore(MAX_CONCURRENT_PER_IP)
            _sems[key] = sem
        return sem


@contextmanager
def public_download_slot(peer_host: str | None, headers: dict[str, str]) -> Iterator[bool]:
    """Yield True if slot acquired; False if over concurrent cap."""
    ip = client_key(peer_host, headers)
    sem = _sem_for(ip)
    if not sem.acquire(blocking=False):
        yield False
        return
    try:
        yield True
    finally:
        sem.release()