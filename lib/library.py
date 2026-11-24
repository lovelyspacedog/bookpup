"""Saved library index and files."""

from __future__ import annotations

import json
import secrets
import shutil
import tempfile
import time
from pathlib import Path

from .core import ensure_dirs
from .json_atomic import atomic_write_json
from . import user_paths
from . import covers
from . import file_digest
from .quota import assert_can_store, library_usage, storage_transaction
from .staging import extract_for_library, staging_dir

READABLE_FORMATS = frozenset(
    {
        "epub",
        "pdf",
        "txt",
        "mobi",
        "azw3",
        "azw",
        "prc",
        "cbz",
        "cbr",
        "cb7",
        "fb2",
        "lit",
        "chm",
        "rtf",
        "djvu",
        "md",
        "html",
    }
)
REGISTERED_SOURCES = frozenset({"calibre_import", "registered"})
STAGED_SOURCE = "download"


def _norm_format(fmt: str) -> str:
    f = fmt.strip().strip('"').strip("'").lstrip(".").lower()
    if f == "htm":
        return "html"
    return f


def _load_index() -> dict:
    ensure_dirs()
    path = user_paths.library_index()
    if not path.is_file():
        return {"items": []}
    return json.loads(path.read_text())


def _save_index(data: dict) -> None:
    path = user_paths.library_index()
    atomic_write_json(path, data)


def _item_source(row: dict) -> str:
    src = str(row.get("source") or "").strip().lower()
    if src in REGISTERED_SOURCES:
        return src if src == "calibre_import" else "registered"
    return STAGED_SOURCE


def is_registered(row: dict) -> bool:
    return str(row.get("source") or "").strip().lower() in REGISTERED_SOURCES


def is_staged(row: dict) -> bool:
    return _item_source(row) == STAGED_SOURCE


def _enrich_row(row: dict) -> dict:
    row["format"] = _norm_format(str(row.get("format") or ""))
    row["source"] = _item_source(row)
    cid = str(row.get("id") or "")
    row["has_cover"] = covers.resolve_cover_path(cid) is not None
    return row


def _row_has_file(row: dict) -> bool:
    fn = str(row.get("filename") or "").strip()
    if not fn:
        return False
    path = user_paths.library_dir() / fn
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def prune_ghost_items() -> int:
    """Drop index rows whose book file is missing (e.g. after a partial wipe)."""
    data = _load_index()
    items = list(data.get("items") or [])
    kept: list[dict] = []
    removed_ids: list[str] = []
    for row in items:
        if not isinstance(row, dict):
            continue
        if _row_has_file(row):
            kept.append(row)
            continue
        iid = str(row.get("id") or "").strip()
        if iid:
            removed_ids.append(iid)
    removed = len(items) - len(kept)
    if removed <= 0:
        return 0
    data["items"] = kept
    _save_index(data)
    for iid in removed_ids:
        covers.remove_covers(iid)
        try:
            from .reading import delete_item_state

            delete_item_state(iid)
        except (OSError, KeyError):
            pass
        try:
            from .convert import delete_derived

            delete_derived(iid)
        except OSError:
            pass
    return removed


def list_items(*, prune: bool = True) -> list[dict]:
    if prune:
        prune_ghost_items()
    data = _load_index()
    items = data.get("items") or []
    items.sort(key=lambda x: x.get("saved_at", 0), reverse=True)
    return [_enrich_row(dict(row)) for row in items]


def cover_path(item_id: str) -> Path:
    path = covers.resolve_cover_path(item_id)
    if path is not None:
        return path
    return user_paths.covers_dir() / f"{item_id}.jpg"


def set_cover(item_id: str, data: bytes) -> dict:
    _find_item(item_id)
    item_path(item_id)
    old = covers.resolve_cover_path(item_id)
    old_len = old.stat().st_size if old and old.is_file() else 0
    delta = len(data) - old_len
    with storage_transaction():
        if delta > 0:
            assert_can_store(delta)
        covers.save_cover(item_id, data)
    row, items, idx = _find_item(item_id)
    row["has_cover"] = True
    items[idx] = row
    _save_index({"items": items})
    return _enrich_row(row)


def set_cover_from_url(item_id: str, url: str) -> dict:
    from .metadata_search import fetch_cover_bytes

    data = fetch_cover_bytes(url)
    return set_cover(item_id, data)


def add_bytes(
    title: str,
    data: bytes,
    fmt: str,
    *,
    source: str = "calibre_import",
    cover: bytes | None = None,
    authors: str | None = None,
    series: str | None = None,
    series_index: float | None = None,
    tags: str | None = None,
    publisher: str | None = None,
    pubdate: str | None = None,
) -> dict:
    fmt = _norm_format(fmt)
    if fmt not in READABLE_FORMATS:
        raise ValueError(f"Unsupported library format: {fmt}")
    extra = len(cover or b"")
    item_id = secrets.token_urlsafe(10)
    ext = f".{fmt}" if fmt else ".bin"
    dest_name = f"{item_id}{ext}"
    dest = user_paths.library_dir() / dest_name
    with storage_transaction():
        assert_can_store(len(data) + extra)
        user_paths.library_dir().mkdir(parents=True, exist_ok=True)
        user_paths.covers_dir().mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        has_cover = False
        if cover and len(cover) > 32:
            covers.save_cover(item_id, cover)
            has_cover = True
    item = {
        "id": item_id,
        "title": (title or dest_name).strip() or dest_name,
        "filename": dest_name,
        "bytes": dest.stat().st_size,
        "format": fmt,
        "saved_at": time.time(),
        "source": source if source == "calibre_import" else "download",
        "authors": (authors or "").strip(),
        "series": (series or "").strip(),
        "series_index": series_index,
        "tags": (tags or "").strip(),
        "publisher": (publisher or "").strip(),
        "pubdate": (pubdate or "").strip(),
        "isbn": "",
        "comments": "",
        "has_cover": has_cover,
    }
    idx = _load_index()
    idx.setdefault("items", []).append(item)
    _save_index(idx)
    if source in REGISTERED_SOURCES:
        try:
            ensure_file_digests(item_id)
        except OSError:
            pass
    return _enrich_row(item)


def clone_item_copy(src_row: dict, file_data: bytes, cover_data: bytes | None = None) -> dict:
    """Copy a library row + bytes into the current user's library (new id)."""
    fmt = _norm_format(str(src_row.get("format") or ""))
    if fmt not in READABLE_FORMATS:
        raise ValueError(f"Unsupported library format: {fmt}")
    extra = len(cover_data or b"")
    source = _item_source(src_row)
    item_id = secrets.token_urlsafe(10)
    ext = f".{fmt}" if fmt else ".bin"
    dest_name = f"{item_id}{ext}"
    dest = user_paths.library_dir() / dest_name
    with storage_transaction():
        assert_can_store(len(file_data) + extra)
        user_paths.library_dir().mkdir(parents=True, exist_ok=True)
        user_paths.covers_dir().mkdir(parents=True, exist_ok=True)
        dest.write_bytes(file_data)
        has_cover = False
        if cover_data and len(cover_data) > 32:
            covers.save_cover(item_id, cover_data)
            has_cover = True
    item = {
        "id": item_id,
        "title": (str(src_row.get("title") or dest_name).strip() or dest_name),
        "filename": dest_name,
        "bytes": dest.stat().st_size,
        "format": fmt,
        "saved_at": time.time(),
        "source": source,
        "authors": (str(src_row.get("authors") or "")).strip(),
        "series": (str(src_row.get("series") or "")).strip(),
        "series_index": src_row.get("series_index"),
        "tags": (str(src_row.get("tags") or "")).strip(),
        "publisher": (str(src_row.get("publisher") or "")).strip(),
        "pubdate": (str(src_row.get("pubdate") or "")).strip(),
        "isbn": (str(src_row.get("isbn") or "")).strip(),
        "comments": (str(src_row.get("comments") or "")).strip(),
        "has_cover": has_cover or bool(src_row.get("has_cover")),
    }
    if has_cover:
        item["has_cover"] = True
    idx = _load_index()
    idx.setdefault("items", []).append(item)
    _save_index(idx)
    if is_registered(item):
        try:
            ensure_file_digests(item_id)
        except OSError:
            pass
    return _enrich_row(item)


UPLOAD_EXTS = frozenset(
    {
        ".epub",
        ".pdf",
        ".mobi",
        ".azw3",
        ".azw",
        ".prc",
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
    }
    | {".zip", ".rar", ".7z", ".tar", ".gz"}
)


def add_upload(data: bytes, original_name: str, title_hint: str | None = None) -> dict:
    """Add a user-uploaded file to Fresh catches (staged / download source)."""
    name = Path(str(original_name or "upload.bin")).name
    if not name or name in (".", ".."):
        raise ValueError("Invalid filename")
    ext = Path(name).suffix.lower()
    if ext not in UPLOAD_EXTS:
        raise ValueError(
            f"Unsupported file type ({ext or 'none'}). "
            "Use a supported ebook/comic type or a zip/rar/7z archive."
        )
    if len(data) > 2 * 1024 * 1024 * 1024:
        raise ValueError("File too large (2 GB max)")
    tmp_path: Path | None = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix="bookpup-up-", suffix=ext or ".bin")
        tmp_path = Path(tmp_name)
        with open(fd, "wb") as out:
            out.write(data)
        extracted, size = extract_for_library(tmp_path)
        with storage_transaction():
            assert_can_store(size)
            item_id = secrets.token_urlsafe(10)
            out_ext = (extracted.suffix or ext or ".bin").replace('"', "")
            dest_name = f"{item_id}{out_ext}"
            dest = user_paths.library_dir() / dest_name
            user_paths.library_dir().mkdir(parents=True, exist_ok=True)
            shutil.copy2(extracted, dest)
            dup = _duplicate_partial_match(dest)
            if dup:
                dest.unlink(missing_ok=True)
                existing = str(dup.get("title") or "another book")
                raise ValueError(f"You already have this file in your kennel as “{existing}”.")
            stem = Path(name).stem
            title = (title_hint or stem or dest_name).strip() or dest_name
            item = {
                "id": item_id,
                "title": title,
                "filename": dest_name,
                "bytes": dest.stat().st_size,
                "format": _norm_format(dest.suffix),
                "saved_at": time.time(),
                "source": "download",
                "authors": "",
                "series": "",
                "tags": "",
                "publisher": "",
                "pubdate": "",
                "isbn": "",
                "comments": "",
                "has_cover": False,
            }
            idx = _load_index()
            idx.setdefault("items", []).append(item)
            _save_index(idx)
            return _enrich_row(item)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)


def find_item_by_staging(staging_id: str) -> dict | None:
    sid = str(staging_id or "").strip()
    if not sid:
        return None
    for row in list_items():
        if str(row.get("staging_id") or "") == sid:
            return row
    return None


def auto_stash_from_job(job: dict) -> dict | None:
    """Move a finished IRC download into Fresh catches (idempotent)."""
    if str(job.get("type") or "") != "download":
        return None
    staging_id = str(job.get("staging_id") or job.get("id") or "").strip()
    if not staging_id or not int(job.get("raw_bytes") or 0):
        return None
    existing = find_item_by_staging(staging_id)
    if existing:
        return existing
    title = str(job.get("title") or "").strip() or None
    try:
        return save_from_staging(staging_id, title)
    except ValueError:
        return find_item_by_staging(staging_id)
    except (KeyError, OSError):
        return None


def save_from_staging(staging_id: str, title_hint: str | None = None) -> dict:
    base = staging_dir(staging_id)
    if not base.is_dir():
        raise KeyError(staging_id)
    raw_candidates = sorted(base.glob("raw*"), key=lambda p: p.stat().st_size, reverse=True)
    if not raw_candidates:
        raise ValueError("No staged raw file")
    raw = raw_candidates[0]
    extracted, size = extract_for_library(raw)
    with storage_transaction():
        assert_can_store(size)
        item_id = secrets.token_urlsafe(10)
        ext = (extracted.suffix or Path(raw.name).suffix or ".bin").replace('"', "")
        dest_name = f"{item_id}{ext}"
        dest = user_paths.library_dir() / dest_name
        user_paths.library_dir().mkdir(parents=True, exist_ok=True)
        shutil.copy2(extracted, dest)
        dup = _duplicate_partial_match(dest)
        if dup:
            dest.unlink(missing_ok=True)
            existing = str(dup.get("title") or "another book")
            raise ValueError(f"You already have this file in your kennel as “{existing}”.")
        title = title_hint or extracted.name
        item = {
            "id": item_id,
            "title": title,
            "filename": dest_name,
            "bytes": dest.stat().st_size,
            "format": _norm_format(dest.suffix),
            "saved_at": time.time(),
            "staging_id": staging_id,
            "source": "download",
            "authors": "",
            "series": "",
            "tags": "",
            "publisher": "",
            "pubdate": "",
            "isbn": "",
            "comments": "",
            "has_cover": False,
        }
        data = _load_index()
        data.setdefault("items", []).append(item)
        _save_index(data)
        return _enrich_row(item)


def _duplicate_partial_match(path: Path) -> dict | None:
    from . import file_digest

    try:
        partial = file_digest.partial_md5(path).lower()
    except OSError:
        return None
    if not partial:
        return None
    for row in list_items():
        if str(row.get("partial_md5") or "").lower() == partial:
            return row
    try:
        for row in list_items():
            other = user_paths.library_dir() / str(row.get("filename") or "")
            if not other.is_file():
                continue
            if file_digest.partial_md5(other).lower() == partial:
                return row
    except OSError:
        pass
    return None


def _find_item(item_id: str) -> tuple[dict, list[dict], int]:
    data = _load_index()
    items = data.get("items") or []
    for i, row in enumerate(items):
        if row.get("id") == item_id:
            return row, items, i
    raise KeyError(item_id)


def _apply_metadata_fields(row: dict, fields: dict, item_id: str, *, use_cover: bool) -> None:
    title = str(fields.get("title") or row.get("title") or "").strip()
    if not title:
        raise ValueError("title required")
    row["title"] = title
    row["authors"] = str(fields.get("authors") or "").strip()
    row["series"] = str(fields.get("series") or "").strip()
    si = fields.get("series_index")
    row["series_index"] = float(si) if si not in (None, "") else None
    row["tags"] = str(fields.get("tags") or "").strip()
    row["publisher"] = str(fields.get("publisher") or "").strip()
    row["pubdate"] = str(fields.get("pubdate") or "").strip()
    row["isbn"] = str(fields.get("isbn") or "").strip()
    row["comments"] = str(fields.get("comments") or "").strip()
    if use_cover:
        cover_url = str(fields.get("cover_url") or "").strip()
        if cover_url:
            from .metadata_search import fetch_cover_bytes

            blob = fetch_cover_bytes(cover_url)
            covers.save_cover(item_id, blob)
            row["has_cover"] = True


def register_item(item_id: str, fields: dict, *, use_cover: bool = False) -> dict:
    row, items, idx = _find_item(item_id)
    if is_registered(row):
        raise ValueError("Item is already registered")
    if not is_staged(row):
        raise ValueError("Only staged files can be registered")
    _apply_metadata_fields(row, fields, item_id, use_cover=use_cover)
    row["source"] = "registered"
    row["saved_at"] = time.time()
    items[idx] = row
    _save_index({"items": items})
    ensure_file_digests(item_id)
    return _enrich_row(row)


def update_metadata(item_id: str, fields: dict, *, use_cover: bool = False) -> dict:
    row, items, idx = _find_item(item_id)
    if not is_registered(row):
        raise ValueError("Only registered books can be edited")
    _apply_metadata_fields(row, fields, item_id, use_cover=use_cover)
    items[idx] = row
    _save_index({"items": items})
    return _enrich_row(row)


def list_registered_items() -> list[dict]:
    return [row for row in list_items() if is_registered(row)]


def get_item_row(item_id: str) -> dict:
    row, _, _ = _find_item(item_id)
    return _enrich_row(dict(row))


def ensure_file_digests(item_id: str) -> dict:
    row, items, idx = _find_item(item_id)
    path = user_paths.library_dir() / row["filename"]
    if not path.is_file():
        raise KeyError(item_id)
    partial = file_digest.partial_md5(path)
    fname = file_digest.filename_md5(path.name)
    if row.get("partial_md5") != partial or row.get("filename_md5") != fname:
        row["partial_md5"] = partial
        row["filename_md5"] = fname
        items[idx] = row
        _save_index({"items": items})
    return _enrich_row(row)


def set_file_digests(item_id: str, partial: str, filename_md5: str) -> None:
    row, items, idx = _find_item(item_id)
    row["partial_md5"] = partial
    row["filename_md5"] = filename_md5
    items[idx] = row
    _save_index({"items": items})


def ensure_all_registered_digests() -> dict[str, str]:
    """Compute KOReader partial MD5 for every registered book; return partial → item_id."""
    index: dict[str, str] = {}
    for row in list_registered_items():
        item_id = str(row.get("id") or "")
        if not item_id:
            continue
        try:
            enriched = ensure_file_digests(item_id)
        except (KeyError, OSError):
            continue
        partial = str(enriched.get("partial_md5") or "").lower()
        if partial:
            index[partial] = item_id
    return index


def item_id_for_document(document: str) -> str | None:
    doc = (document or "").strip().lower()
    if not doc:
        return None
    index = ensure_all_registered_digests()
    return index.get(doc)


def _reading_location_from_koreader(row: dict, progress: str | None, percentage: float | None) -> dict | None:
    fmt = _norm_format(str(row.get("format") or ""))
    prog = (progress or "").strip()
    if fmt == "pdf":
        page = None
        if prog.isdigit():
            page = int(prog)
        elif row.get("koreader_page"):
            page = int(row["koreader_page"])
        if page and page > 0:
            return {"type": "pdf", "page": page}
    if percentage is not None:
        return {"type": "koreader", "progress": prog, "percentage": percentage}
    if prog:
        return {"type": "koreader", "progress": prog}
    return None


def apply_koreader_progress(
    item_id: str,
    *,
    progress: str | None,
    percentage: float | None,
    device: str,
    device_id: str = "",
    synced_at: int,
    document_id: str | None = None,
) -> dict:
    row, items, idx = _find_item(item_id)
    if not is_registered(row):
        raise ValueError("KOReader sync applies to registered books only")
    ensure_file_digests(item_id)
    if document_id:
        row["partial_md5"] = document_id.lower()
    if percentage is not None:
        row["koreader_percentage"] = float(percentage)
    if progress is not None:
        row["koreader_progress"] = str(progress)
    row["koreader_device"] = str(device)[:120]
    row["koreader_device_id"] = str(device_id)[:64]
    row["koreader_synced_at"] = synced_at
    items[idx] = row
    _save_index({"items": items})
    loc = _reading_location_from_koreader(row, progress, percentage)
    if loc:
        from .reading import set_location

        set_location(item_id, loc)
    return _enrich_row(row)


def apply_koreader_sidecar(
    item_id: str,
    *,
    percentage: float | None,
    progress: str | None,
    status: str | None,
    highlights: str | None,
    stats_title: str | None,
    sidecar_name: str,
) -> dict:
    row, items, idx = _find_item(item_id)
    if not is_registered(row):
        raise ValueError("KOReader import applies to registered books only")
    ensure_file_digests(item_id)
    if percentage is not None:
        row["koreader_percentage"] = float(percentage)
    if progress:
        row["koreader_progress"] = str(progress)
    if status:
        row["koreader_status"] = status
    if highlights:
        row["koreader_highlights"] = highlights
    if stats_title and not str(row.get("title") or "").strip():
        row["title"] = stats_title
    row["koreader_sidecar_imported_at"] = time.time()
    row["koreader_sidecar_name"] = sidecar_name[:200]
    items[idx] = row
    _save_index({"items": items})
    loc = _reading_location_from_koreader(row, progress, percentage)
    if loc:
        from .reading import set_location

        set_location(item_id, loc)
    return {"item": _enrich_row(row), "item_id": item_id, "sidecar": sidecar_name}


def delete_item(item_id: str) -> None:
    data = _load_index()
    items = data.get("items") or []
    kept = []
    removed = None
    for row in items:
        if row.get("id") == item_id:
            removed = row
        else:
            kept.append(row)
    if not removed:
        raise KeyError(item_id)
    path = user_paths.library_dir() / removed["filename"]
    if path.is_file():
        path.unlink()
    covers.remove_covers(item_id)
    try:
        from .convert import delete_derived

        delete_derived(item_id)
    except OSError:
        pass
    try:
        from .reading import delete_item_state

        delete_item_state(item_id)
    except (OSError, KeyError):
        pass
    data["items"] = kept
    _save_index(data)
    try:
        from . import shelves as shelves_mod

        shelves_mod.remove_item_from_all_shelves(item_id)
    except OSError:
        pass


def item_path(item_id: str) -> Path:
    for row in list_items():
        if row.get("id") == item_id:
            p = user_paths.library_dir() / row["filename"]
            if p.is_file():
                return p
    raise KeyError(item_id)


def status() -> dict:
    usage = library_usage()
    pruned = prune_ghost_items()
    items = list_items(prune=False)
    from . import shelves as shelves_mod

    out: dict = {
        "items": items,
        "readable_formats": sorted(READABLE_FORMATS),
        "shelves": shelves_mod.list_shelves(),
        **usage,
    }
    if pruned:
        out["pruned_ghosts"] = pruned
    return out