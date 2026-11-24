"""Soulseek download via slskd into BookPup staging."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from . import jobs, slskd_client
from .slskd_client import SlskdError
from .staging import create_staging

_FIND_SCAN_MAX = 8000


def _remote_parent_name(path: str) -> str:
    p = path.replace("\\", "/").strip()
    if "/" not in p:
        return ""
    return p.rsplit("/", 1)[0].rsplit("/", 1)[-1]


def _find_under_root(base: Path, basename: str, *, size_hint: int = 0) -> Path | None:
    name_key = basename.casefold()
    hits: list[Path] = []
    scanned = 0
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        scanned += 1
        if scanned > _FIND_SCAN_MAX:
            break
        if path.name.casefold() != name_key:
            continue
        hits.append(path)
    if not hits:
        return None
    if size_hint > 0:
        sized = [p for p in hits if p.stat().st_size == size_hint]
        if sized:
            hits = sized
    if len(hits) == 1:
        return hits[0]
    hits.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0]


def _resolve_local_file(transfer: dict, filename: str) -> Path:
    for key in ("localPath", "path", "fullPath", "local_path"):
        raw = transfer.get(key)
        if raw:
            p = Path(str(raw))
            if p.is_file():
                return p
    root = slskd_client.download_root()
    if not root:
        raise SlskdError("slskd_download_root not configured on server")
    base = Path(root)
    if not base.is_dir():
        raise SlskdError(f"slskd download root missing: {base}")
    fn = filename.replace("\\", "/").strip()
    base_name = Path(fn).name
    parent = _remote_parent_name(fn)
    try:
        size_hint = int(transfer.get("size") or transfer.get("bytesTransferred") or 0)
    except (TypeError, ValueError):
        size_hint = 0
    candidates = [
        base / fn,
        base / base_name,
    ]
    if parent:
        candidates.append(base / parent / base_name)
    # slskd often keeps one folder level from the remote tree (not the full path)
    for cand in candidates:
        if cand.is_file():
            return cand
    # slskd may nest under username folder
    user = str(transfer.get("username") or "").strip()
    if user:
        candidates.append(base / user / base_name)
        candidates.append(base / user / fn)
        for cand in candidates:
            if cand.is_file():
                return cand
    found = _find_under_root(base, base_name, size_hint=size_hint)
    if found:
        return found
    raise SlskdError("Completed download file not found on disk; check slskd_download_root")


def run_download_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    sk = job.get("soulseek")
    if not isinstance(sk, dict):
        raise SlskdError("Soulseek metadata missing on job")
    username = str(sk.get("username") or "").strip()
    filename = str(sk.get("filename") or "").strip()
    try:
        size = int(sk.get("size") or 0)
    except (TypeError, ValueError):
        size = 0
    if not username or not filename:
        raise SlskdError("Incomplete Soulseek row on job")

    staging_id = str(job.get("staging_id") or job_id)
    create_staging(staging_id)
    dest_dir = create_staging(staging_id)

    def tick(payload: dict[str, Any]) -> None:
        state = str(payload.get("state") or payload.get("status") or "")
        jobs.set_irc_status(job_id, f"Soulseek fetch: {state or '…'}")

    jobs.set_irc_status(job_id, f"Queueing Soulseek fetch from {username}…")
    transfer_id = slskd_client.queue_download(username, filename, size)
    sk["transfer_id"] = transfer_id
    job["soulseek"] = sk
    jobs.save_job(job)

    transfer = slskd_client.wait_download_complete(username, transfer_id, on_tick=tick)
    src = _resolve_local_file(transfer, filename)
    ext = Path(_basename(filename)).suffix or Path(src.suffix or ".bin")
    if not ext.startswith("."):
        ext = "." + ext
    dest = dest_dir / f"raw{ext}"
    shutil.copy2(src, dest)
    job = jobs.load_job(job_id)
    job["staging_id"] = staging_id
    job["raw_name"] = dest.name
    job["raw_bytes"] = dest.stat().st_size
    jobs.save_job(job)


def _basename(path: str) -> str:
    p = path.replace("\\", "/").strip()
    if "/" in p:
        return p.rsplit("/", 1)[-1]
    return p