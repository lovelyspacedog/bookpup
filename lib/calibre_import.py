"""Import books from Calibre export part-*.calibre-data files."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from . import library
from .library import READABLE_FORMATS, _norm_format

PART_NAME_RE = re.compile(r"^part-(\d+)\.calibre-data$", re.IGNORECASE)
FORMAT_PREF = (
    "epub",
    "azw3",
    "mobi",
    "azw",
    "prc",
    "pdf",
    "fb2",
    "djvu",
    "chm",
    "rtf",
    "lit",
    "cbz",
    "cbr",
    "cb7",
    "md",
    "html",
    "txt",
)
SKIP_FORMATS = frozenset({".cover", "cover", "jpg", "jpeg", "png", "opf"})

_BOOK_META_SQL = """
SELECT
    b.title,
    b.series_index,
    b.pubdate,
    (SELECT group_concat(a.name, ' & ')
     FROM books_authors_link AS bal
     JOIN authors AS a ON a.id = bal.author
     WHERE bal.book = b.id) AS authors,
    (SELECT s.name
     FROM books_series_link AS bsl
     JOIN series AS s ON s.id = bsl.series
     WHERE bsl.book = b.id
     LIMIT 1) AS series,
    (SELECT group_concat(t.name, ', ')
     FROM books_tags_link AS btl
     JOIN tags AS t ON t.id = btl.tag
     WHERE btl.book = b.id) AS tags,
    (SELECT p.name
     FROM books_publishers_link AS bpl
     JOIN publishers AS p ON p.id = bpl.publisher
     WHERE bpl.book = b.id
     LIMIT 1) AS publisher
FROM books AS b
WHERE b.id = ?
"""


def _json_object_end(data: bytes) -> int:
    depth = 0
    for i, b in enumerate(data):
        if b == ord("{"):
            depth += 1
        elif b == ord("}"):
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("Incomplete JSON in calibre-data part")


def _index_parts(paths: list[Path]) -> dict[int, Path]:
    out: dict[int, Path] = {}
    for path in paths:
        m = PART_NAME_RE.match(path.name)
        if not m:
            raise ValueError(f"Expected part-NNNN.calibre-data, got {path.name}")
        out[int(m.group(1))] = path
    if not out:
        raise ValueError("No calibre-data parts")
    return out


def _load_file_metadata(parts: dict[int, Path]) -> dict:
    for path in parts.values():
        with path.open("rb") as fh:
            head = fh.read(16)
        if head.startswith(b"SQLite format 3"):
            continue
        data = path.read_bytes()
        if b'"file_metadata"' not in data[:65536]:
            continue
        end = _json_object_end(data)
        meta = json.loads(data[:end].decode("utf-8"))
        if "file_metadata" in meta:
            return meta
    raise ValueError("No file_metadata found in export parts")


def _open_catalog(parts: dict[int, Path]) -> sqlite3.Connection:
    for idx in sorted(parts):
        p = parts[idx]
        with p.open("rb") as fh:
            head = fh.read(16)
        if head.startswith(b"SQLite format 3"):
            return sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    raise ValueError("No SQLite catalog (metadata.db) in export parts")


def _library_hex(meta: dict) -> str:
    libs = meta.get("libraries")
    if isinstance(libs, list) and libs:
        lib_path = str(libs[0])
    elif isinstance(libs, dict) and libs:
        lib_path = str(next(iter(libs)))
    else:
        lib_path = ""
        for key in meta:
            if isinstance(key, str) and (key.startswith("/") or key.startswith("~")):
                lib_path = key
                break
    if not lib_path:
        raise ValueError("No library path in export metadata")
    return lib_path.encode("utf-8").hex()


def _pick_format(formats: list[str]) -> str | None:
    normed = {_norm_format(f) for f in formats}
    for pref in FORMAT_PREF:
        if pref in normed:
            return pref
    for fmt in normed:
        if fmt in READABLE_FORMATS:
            return fmt
    return None


def _read_blob(parts: dict[int, Path], spec: list) -> bytes:
    part_idx = int(spec[0])
    offset = int(spec[1])
    length = int(spec[2])
    sha1 = str(spec[3]) if len(spec) > 3 and spec[3] else ""
    path = parts.get(part_idx)
    if not path:
        raise ValueError(f"Export missing part-{part_idx:04d}.calibre-data")
    with path.open("rb") as fh:
        fh.seek(offset)
        blob = fh.read(length)
    if len(blob) != length:
        raise ValueError(f"Short read for part {part_idx} at {offset}")
    if sha1 and hashlib.sha1(blob).hexdigest() != sha1:
        raise ValueError("Checksum mismatch for exported book file")
    return blob


def _fmt_pubdate(raw: object) -> str:
    if raw is None:
        return ""
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(float(raw), tz=timezone.utc).strftime("%Y-%m-%d")
        except (OSError, OverflowError, ValueError):
            return ""
    text = str(raw).strip()
    return text[:32]


def _book_details(con: sqlite3.Connection, book_id: int) -> dict:
    row = con.execute(_BOOK_META_SQL, (book_id,)).fetchone()
    if not row:
        return {}
    title, series_index, pubdate, authors, series, tags, publisher = row
    return {
        "title": title or f"Book {book_id}",
        "authors": authors or "",
        "series": series or "",
        "series_index": float(series_index) if series_index is not None else None,
        "tags": tags or "",
        "publisher": publisher or "",
        "pubdate": _fmt_pubdate(pubdate),
    }


def _optional_cover(parts: dict[int, Path], file_meta: dict, lib_hex: str, book_id: int) -> bytes | None:
    for suffix in (".cover", "JPEG", "JPG", "PNG"):
        key = f"{lib_hex}:{book_id}:{suffix}"
        spec = file_meta.get(key)
        if spec:
            try:
                return _read_blob(parts, spec)
            except (ValueError, OSError):
                return None
    return None


def import_parts(part_paths: list[Path]) -> dict:
    """Import readable books from Calibre export parts into the library."""
    paths = [Path(p) for p in part_paths]
    parts = _index_parts(paths)
    meta = _load_file_metadata(parts)
    lib_hex = _library_hex(meta)
    file_meta: dict = meta["file_metadata"]
    con = _open_catalog(parts)
    try:
        rows = con.execute(
            """
            SELECT b.id, b.title, d.format
            FROM books AS b
            JOIN data AS d ON d.book = b.id
            ORDER BY b.id, d.format
            """
        ).fetchall()
    finally:
        con.close()

    by_book: dict[int, dict] = {}
    for book_id, title, fmt in rows:
        norm = _norm_format(fmt)
        if norm in SKIP_FORMATS:
            continue
        slot = by_book.setdefault(int(book_id), {"title": title or f"Book {book_id}", "formats": []})
        slot["formats"].append(fmt)

    con = _open_catalog(parts)
    imported = 0
    skipped = 0
    errors: list[dict] = []

    try:
        for book_id, info in sorted(by_book.items()):
            pick = _pick_format(info["formats"])
            if not pick:
                skipped += 1
                continue
            fmt_key = pick.upper()
            key = f"{lib_hex}:{book_id}:{fmt_key}"
            spec = file_meta.get(key)
            if not spec:
                errors.append(
                    {"book_id": book_id, "title": info["title"], "error": f"No export blob for {fmt_key}"}
                )
                continue
            try:
                blob = _read_blob(parts, spec)
                details = _book_details(con, book_id)
                cover = _optional_cover(parts, file_meta, lib_hex, book_id)
                library.add_bytes(
                    details.get("title") or info["title"],
                    blob,
                    pick,
                    source="calibre_import",
                    cover=cover,
                    authors=details.get("authors"),
                    series=details.get("series"),
                    series_index=details.get("series_index"),
                    tags=details.get("tags"),
                    publisher=details.get("publisher"),
                    pubdate=details.get("pubdate"),
                )
                imported += 1
            except ValueError as exc:
                msg = str(exc)
                if "quota" in msg.lower():
                    errors.append({"book_id": book_id, "title": info["title"], "error": msg})
                    break
                errors.append({"book_id": book_id, "title": info["title"], "error": msg})
            except OSError as exc:
                errors.append({"book_id": book_id, "title": info["title"], "error": str(exc)})
    finally:
        con.close()

    return {
        "ok": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "library": library.status(),
    }