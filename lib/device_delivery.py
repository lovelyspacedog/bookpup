"""Resolve catalogued books for e-reader / Kindle sideload delivery."""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path

from .convert import VIEW_CALIBRE_CONVERT, VIEW_MOBILE_CONVERT, VIEW_NATIVE, item_format, prepare_view
from .library import item_path, list_items

_DELIVERY_CHOICES = frozenset({"source", "epub", "pdf"})


def _safe_stem(title: str, fallback: str) -> str:
    raw = (title or fallback or "book").strip()[:120]
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", raw)
    return safe or "book"


def _row_for(item_id: str) -> dict:
    for row in list_items():
        if row.get("id") == item_id:
            return row
    raise KeyError(item_id)


def _mime_for(fmt: str, path: Path) -> str:
    fixed = {
        "pdf": "application/pdf",
        "epub": "application/epub+zip",
        "mobi": "application/x-mobipocket-ebook",
        "azw3": "application/vnd.amazon.ebook",
        "azw": "application/vnd.amazon.ebook",
        "prc": "application/x-mobipocket-ebook",
    }.get(fmt)
    if fixed:
        return fixed
    guess = mimetypes.guess_type(path.name)[0]
    return guess or "application/octet-stream"


def delivery_options(item_id: str) -> list[dict]:
    fmt = item_format(item_id)
    row = _row_for(item_id)
    title = str(row.get("title") or row.get("filename") or "Book")
    opts: list[dict] = []
    opts.append(
        {
            "id": "source",
            "label": f"Original ({fmt.upper()})",
            "hint": "File as stored in your kennel.",
        }
    )
    can_epub = fmt == "epub" or fmt in VIEW_MOBILE_CONVERT or fmt in VIEW_CALIBRE_CONVERT
    if can_epub and fmt != "epub":
        opts.append(
            {
                "id": "epub",
                "label": "EPUB",
                "hint": "Converted for KOReader or Kindle (EPUB).",
            }
        )
    if fmt == "pdf":
        opts.append(
            {
                "id": "pdf",
                "label": "PDF",
                "hint": "Same as original PDF.",
            }
        )
    elif fmt in VIEW_NATIVE and fmt not in ("pdf", "epub"):
        pass
    _ = title
    return opts


def resolve_delivery(item_id: str, choice: str) -> tuple[Path, str, str]:
    choice = str(choice or "").strip().lower()
    if choice not in _DELIVERY_CHOICES:
        raise ValueError("Invalid delivery format")
    options = {o["id"] for o in delivery_options(item_id)}
    if choice not in options:
        raise ValueError("That format is not available for this book")
    row = _row_for(item_id)
    stem = _safe_stem(str(row.get("title") or ""), str(row.get("filename") or item_id))
    src = item_path(item_id)
    fmt = item_format(item_id)
    if choice == "source":
        ext = fmt or src.suffix.lstrip(".") or "bin"
        return src, _mime_for(fmt, src), f"{stem}.{ext}"
    if choice == "epub":
        meta = prepare_view(item_id)
        if meta.get("format") != "epub":
            raise ValueError("EPUB delivery failed")
        path = Path(meta["path"])
        return path, "application/epub+zip", f"{stem}.epub"
    if choice == "pdf":
        if fmt != "pdf":
            raise ValueError("PDF delivery only for PDF books")
        return src, "application/pdf", f"{stem}.pdf"
    raise ValueError("Invalid delivery format")