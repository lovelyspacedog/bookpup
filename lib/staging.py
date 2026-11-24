"""Transient download staging and archive extraction."""

from __future__ import annotations

import re
import shutil
import time
import zipfile
from pathlib import Path

from . import core
from .core import STAGING_TTL_SECONDS, ensure_dirs
from .safe_ids import path_under, validate_path_segment

EBOOK_EXTS = (
    ".epub",
    ".pdf",
    ".mobi",
    ".azw3",
    ".cbz",
    ".cbr",
    ".cb7",
    ".txt",
    ".md",
    ".html",
    ".htm",
    ".djvu",
    ".fb2",
    ".lit",
    ".chm",
    ".rtf",
)
ARCHIVE_EXTS = (".zip", ".rar", ".7z", ".tar", ".gz", ".cbz", ".cbr", ".cb7")


def staging_dir(staging_id: str) -> Path:
    ensure_dirs()
    sid = validate_path_segment(staging_id, label="staging id")
    return path_under(core.STAGING_DIR, sid)


def create_staging(staging_id: str) -> Path:
    path = staging_dir(staging_id)
    path.mkdir(parents=True, exist_ok=True)
    meta = path / "meta.json"
    if not meta.exists():
        meta.write_text('{"created_at": %f}\n' % time.time())
    return path


def cleanup_staging() -> int:
    ensure_dirs()
    removed = 0
    now = time.time()
    for entry in core.STAGING_DIR.iterdir():
        if not entry.is_dir():
            continue
        meta = entry / "meta.json"
        created = entry.stat().st_mtime
        if meta.is_file():
            try:
                created = float(re.search(r"([\d.]+)", meta.read_text()).group(1))
            except (AttributeError, ValueError):
                pass
        if now - created > STAGING_TTL_SECONDS:
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1
    return removed


def _find_ebook(root: Path) -> Path | None:
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in EBOOK_EXTS:
            candidates.append(path)
    if not candidates:
        return None
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def _safe_extract_zip(zf: zipfile.ZipFile, dest: Path) -> None:
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.startswith("/") or ".." in Path(name).parts:
            raise ValueError("Unsafe path in archive")
        target = (dest / name).resolve()
        if not str(target).startswith(str(dest)):
            raise ValueError("Unsafe path in archive")
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, target.open("wb") as out:
            shutil.copyfileobj(src, out, 8 * 1024 * 1024)


def _extract_archive(archive: Path, dest: Path) -> None:
    suffix = archive.suffix.lower()
    if suffix == ".zip" or zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            _safe_extract_zip(zf, dest)
        return
    # .rar/.7z: copy as-is when no extractor is available
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, dest / archive.name)


def extract_for_library(raw_path: Path) -> tuple[Path, int]:
    """Return (file_to_store, byte_size)."""
    raw_path = raw_path.resolve()
    if not raw_path.is_file():
        raise ValueError("missing staged file")
    suffix = raw_path.suffix.lower()
    if suffix in ARCHIVE_EXTS and suffix != ".epub":
        work = raw_path.parent / "_extract"
        if work.exists():
            shutil.rmtree(work)
        work.mkdir()
        _extract_archive(raw_path, work)
        found = _find_ebook(work)
        if found:
            return found, found.stat().st_size
    if suffix in EBOOK_EXTS or raw_path.is_file():
        return raw_path, raw_path.stat().st_size
    raise ValueError("No readable ebook found in download")