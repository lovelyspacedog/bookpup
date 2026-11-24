"""Chunked library import upload sessions (Calibre parts, KOReader sidecars)."""

from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path

from .calibre_import import PART_NAME_RE, import_parts
from . import koreader_sidecar
from . import user_paths
from .core import CONFIG_DIR
from .json_atomic import atomic_write_json

IMPORT_SESSIONS_DIR = CONFIG_DIR / "import-sessions"
CHUNK_SIZE = 4 * 1024 * 1024
SESSION_TTL_SECONDS = 24 * 3600
KOREADER_PART_RE = re.compile(r"^.+\.(lua|zip)$", re.IGNORECASE)


def _session_dir(session_id: str) -> Path:
    if not session_id or "/" in session_id or ".." in session_id:
        raise ValueError("Invalid session id")
    return IMPORT_SESSIONS_DIR / session_id


def _manifest_path(session_id: str) -> Path:
    return _session_dir(session_id) / "manifest.json"


def cleanup_stale_sessions() -> int:
    IMPORT_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
    removed = 0
    now = time.time()
    for path in IMPORT_SESSIONS_DIR.iterdir():
        if not path.is_dir():
            continue
        manifest = path / "manifest.json"
        if not manifest.is_file():
            path.rmdir()
            removed += 1
            continue
        try:
            data = json.loads(manifest.read_text())
        except (json.JSONDecodeError, OSError):
            data = {}
        if now - float(data.get("created", 0)) > SESSION_TTL_SECONDS:
            for child in path.iterdir():
                child.unlink(missing_ok=True)
            path.rmdir()
            removed += 1
    return removed


def _validate_part_name(name: str, kind: str) -> None:
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError(f"Invalid part name: {name}")
    if kind == "calibre":
        if not PART_NAME_RE.match(name):
            raise ValueError(f"Invalid part name: {name}")
    elif kind == "koreader":
        if not KOREADER_PART_RE.match(name):
            raise ValueError(f"Invalid upload name (use .lua or .zip): {name}")
    else:
        raise ValueError(f"Unknown import kind: {kind}")


def create_session(parts: list[dict], *, kind: str = "calibre") -> dict:
    cleanup_stale_sessions()
    if not parts:
        raise ValueError("No parts listed")
    kind = str(kind or "calibre").strip().lower()
    catalog: dict[str, dict] = {}
    for row in parts:
        name = str(row.get("name") or "").strip()
        _validate_part_name(name, kind)
        size = int(row.get("size") or 0)
        if size <= 0:
            raise ValueError(f"Invalid size for {name}")
        catalog[name] = {"size": size, "received": 0}

    owner = user_paths.current_user()
    session_id = secrets.token_urlsafe(16)
    base = _session_dir(session_id)
    base.mkdir(parents=True, exist_ok=True)
    manifest = {
        "created": time.time(),
        "kind": kind,
        "owner": owner,
        "parts": catalog,
    }
    _manifest_path(session_id).write_text(json.dumps(manifest, indent=2) + "\n")
    total = sum(row["size"] for row in catalog.values())
    return {
        "session_id": session_id,
        "chunk_size": CHUNK_SIZE,
        "total_bytes": total,
        "parts": list(catalog.keys()),
    }


def _load_manifest(session_id: str) -> dict:
    path = _manifest_path(session_id)
    if not path.is_file():
        raise KeyError(session_id)
    return json.loads(path.read_text())


def _save_manifest(session_id: str, manifest: dict) -> None:
    atomic_write_json(_manifest_path(session_id), manifest)


def _assert_session_owner(manifest: dict) -> None:
    owner = str(manifest.get("owner") or "").strip()
    user = user_paths.current_user()
    if not owner or owner != user:
        raise PermissionError("Import session not found")


def session_progress(session_id: str) -> dict:
    manifest = _load_manifest(session_id)
    parts = manifest.get("parts") or {}
    total = sum(int(p.get("size") or 0) for p in parts.values())
    received = sum(int(p.get("received") or 0) for p in parts.values())
    return {
        "session_id": session_id,
        "total_bytes": total,
        "received_bytes": received,
        "complete": received >= total and total > 0,
        "parts": parts,
    }


def write_chunk(session_id: str, part_name: str, offset: int, data: bytes) -> dict:
    manifest = _load_manifest(session_id)
    _assert_session_owner(manifest)
    parts = manifest.get("parts") or {}
    if part_name not in parts:
        raise ValueError(f"Unknown part {part_name}")
    entry = parts[part_name]
    size = int(entry["size"])
    received = int(entry.get("received") or 0)
    if offset != received:
        raise ValueError(f"Expected offset {received}, got {offset}")
    if offset + len(data) > size:
        raise ValueError("Chunk exceeds declared part size")
    dest = _session_dir(session_id) / part_name
    if offset == 0:
        dest.write_bytes(data)
    else:
        with dest.open("r+b") as fh:
            fh.seek(offset)
            fh.write(data)
    entry["received"] = offset + len(data)
    _save_manifest(session_id, manifest)
    prog = session_progress(session_id)
    prog["part"] = part_name
    prog["part_received"] = entry["received"]
    prog["part_size"] = size
    return prog


def finish_session(session_id: str) -> dict:
    manifest = _load_manifest(session_id)
    _assert_session_owner(manifest)
    prog = session_progress(session_id)
    if not prog["complete"]:
        raise ValueError("Upload incomplete")
    manifest = _load_manifest(session_id)
    kind = str(manifest.get("kind") or "calibre").strip().lower()
    base = _session_dir(session_id)
    paths = sorted(
        (p for p in base.iterdir() if p.is_file() and p.name != "manifest.json"),
        key=lambda p: p.name,
    )
    if not paths:
        raise ValueError("No upload files on disk")
    try:
        if kind == "koreader":
            return koreader_sidecar.import_upload(paths)
        calibre_paths = [p for p in paths if PART_NAME_RE.match(p.name)]
        if not calibre_paths:
            raise ValueError("No part-*.calibre-data files in session")
        return import_parts(calibre_paths)
    finally:
        for path in base.iterdir():
            path.unlink(missing_ok=True)
        try:
            base.rmdir()
        except OSError:
            pass