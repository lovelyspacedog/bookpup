"""KOReader Progress Sync (kosync) compatible storage."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from typing import Any

from .core import CONFIG_DIR, ensure_dirs
from . import accounts
from . import file_digest
from . import library
from .json_atomic import atomic_write_json

KOSYNC_STATE = CONFIG_DIR / "kosync.json"
KO_JSON = "application/vnd.koreader.v1+json"
_lock = threading.Lock()
MAX_DOCUMENTS = 5000
DOCUMENT_TTL_SECONDS = 90 * 24 * 3600
_DOCUMENT_RE = re.compile(r"^[0-9a-f]{32}$")


def _load() -> dict:
    ensure_dirs()
    if not KOSYNC_STATE.is_file():
        return {"documents": {}}
    try:
        return json.loads(KOSYNC_STATE.read_text())
    except (json.JSONDecodeError, OSError):
        return {"documents": {}}


def _save(data: dict) -> None:
    ensure_dirs()
    atomic_write_json(KOSYNC_STATE, data)


def _valid_document_id(document: str) -> bool:
    return bool(_DOCUMENT_RE.fullmatch(document))


def _prune_stale_documents(docs: dict) -> None:
    cutoff_ms = int(time.time() * 1000) - DOCUMENT_TTL_SECONDS * 1000
    stale = [
        key
        for key, row in docs.items()
        if not isinstance(row, dict) or int(row.get("timestamp") or 0) < cutoff_ms
    ]
    for key in stale:
        docs.pop(key, None)


def _upsert_document(docs: dict, document: str, row: dict) -> tuple[int, dict] | None:
    is_new = document not in docs
    if is_new:
        _prune_stale_documents(docs)
        if len(docs) >= MAX_DOCUMENTS:
            return 507, {"code": 2005, "message": "Progress store full; try again later"}
    docs[document] = row
    return None


def auth_user(headers: dict[str, str], config: dict) -> str | None:
    user = (headers.get("x-auth-user") or headers.get("X-Auth-User") or "").strip()
    key = (headers.get("x-auth-key") or headers.get("X-Auth-Key") or "").strip().lower()
    if not user or not key:
        return None
    accounts.migrate_legacy()
    row = accounts.get_user(user)
    if not row or not row.get("enabled", True):
        return None
    expected = hashlib.md5(str(row.get("password") or "").encode("utf-8")).hexdigest().lower()
    if key == expected:
        return user
    return None


def unauthorized() -> tuple[int, dict]:
    return 401, {"code": 2001, "message": "Unauthorized"}


def get_progress(document: str) -> tuple[int, dict]:
    document = (document or "").strip().lower()
    if not _valid_document_id(document):
        return 400, {"code": 2002, "message": "Invalid document"}
    with _lock:
        row = (_load().get("documents") or {}).get(document)
    if not row:
        return 200, {}
    out = {k: row[k] for k in ("document", "progress", "percentage", "device", "device_id", "timestamp") if k in row}
    if "timestamp" in out and out["timestamp"] < 10_000_000_000:
        out["timestamp"] = int(out["timestamp"]) * 1000
    return 200, out


def put_progress(body: dict[str, Any]) -> tuple[int, dict]:
    document = str(body.get("document") or "").strip().lower()
    progress = body.get("progress")
    percentage = body.get("percentage")
    device = body.get("device")
    if not _valid_document_id(document):
        return 400, {"code": 2002, "message": "Invalid document"}
    if progress is None or percentage is None or not device:
        return 400, {"code": 2003, "message": "Invalid fields"}
    try:
        percentage = float(percentage)
    except (TypeError, ValueError):
        return 400, {"code": 2003, "message": "Invalid fields"}
    progress = str(progress)
    device = str(device)[:120]
    device_id = str(body.get("device_id") or "").strip()[:64]
    timestamp = int(time.time() * 1000)
    row = {
        "document": document,
        "progress": progress,
        "percentage": percentage,
        "device": device,
        "device_id": device_id,
        "timestamp": timestamp,
    }
    with _lock:
        data = _load()
        docs = data.setdefault("documents", {})
        denied = _upsert_document(docs, document, row)
        if denied:
            return denied
        _save(data)
    item_id = library.item_id_for_document(document)
    if item_id:
        library.apply_koreader_progress(
            item_id,
            progress=progress,
            percentage=percentage,
            device=device,
            device_id=device_id,
            synced_at=int(timestamp / 1000),
            document_id=document,
        )
    return 200, {"document": document, "timestamp": timestamp}


def sync_reading_to_document(item_id: str, *, percentage: float | None, progress: str | None, device: str) -> None:
    row = library.get_item_row(item_id)
    if not row or not library.is_registered(row):
        return
    path = library.item_path(item_id)
    partial = row.get("partial_md5")
    if not partial:
        partial, fname_md5 = file_digest.partial_md5(path), file_digest.filename_md5(path.name)
        library.set_file_digests(item_id, partial, fname_md5)
    else:
        partial = str(partial)
    if percentage is None and progress is None:
        return
    if percentage is None:
        percentage = float(row.get("koreader_percentage") or 0.0)
    if progress is None:
        progress = "0"
    timestamp = int(time.time() * 1000)
    partial = partial.lower()
    if not _valid_document_id(partial):
        return
    row = {
        "document": partial,
        "progress": str(progress),
        "percentage": float(percentage),
        "device": device[:120],
        "device_id": "bookpup-web",
        "timestamp": timestamp,
    }
    with _lock:
        data = _load()
        docs = data.setdefault("documents", {})
        denied = _upsert_document(docs, partial, row)
        if denied:
            return
        _save(data)
    library.apply_koreader_progress(
        item_id,
        progress=str(progress),
        percentage=float(percentage),
        device=device,
        device_id="bookpup-web",
        synced_at=int(timestamp / 1000),
        document_id=partial,
    )


def create_user(body: dict[str, Any], config: dict) -> tuple[int, dict]:
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "").strip().lower()
    accounts.migrate_legacy()
    row = accounts.get_user(username)
    if row:
        expected = hashlib.md5(str(row.get("password") or "").encode("utf-8")).hexdigest().lower()
        if password == expected and row.get("enabled", True):
            return 201, {"username": username}
        if password == expected:
            return 401, {"code": 2001, "message": "Unauthorized"}
        return 402, {"code": 2004, "message": "User exists"}
    cfg_user = str(config.get("username") or "book").strip()
    cfg_pass = hashlib.md5(str(config.get("password") or "").encode("utf-8")).hexdigest().lower()
    if username == cfg_user and password == cfg_pass:
        return 201, {"username": username}
    if username == cfg_user:
        return 402, {"code": 2004, "message": "User exists"}
    return 401, {"code": 2001, "message": "Unauthorized"}