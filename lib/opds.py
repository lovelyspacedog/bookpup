"""Minimal OPDS 1.2 catalog for registered library books."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from .core import public_base_url, load_config
from .library import list_registered_items

ATOM = "http://www.w3.org/2005/Atom"
OPDS = "http://opds-spec.org/kind/acquisition"


def _el(tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    node = ET.Element(tag, attrs)
    if text is not None:
        node.text = text
    return node


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    node = _el(tag, text, **attrs)
    parent.append(node)
    return node


def feed_root(base: str) -> bytes:
    root = _el(
        "feed",
        attrib={
            "xmlns": ATOM,
            "xmlns:opds": OPDS,
        },
    )
    _sub(root, "title", "BookPup catalog")
    _sub(root, "id", f"{base}/opds")
    _sub(root, "updated", "2026-01-01T00:00:00Z")
    entry = _sub(root, "entry")
    _sub(entry, "title", "All registered books")
    _sub(entry, "id", f"{base}/opds/catalog")
    _sub(
        entry,
        "link",
        attrib={
            "rel": "subsection",
            "type": "application/atom+xml;profile=opds-catalog",
            "href": f"{base}/opds/catalog",
        },
    )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def feed_catalog(base: str, username: str) -> bytes:
    cfg = load_config()
    base = public_base_url(cfg) if not base else base
    root = _el(
        "feed",
        attrib={
            "xmlns": ATOM,
            "xmlns:opds": OPDS,
        },
    )
    _sub(root, "title", f"BookPup — {username}")
    _sub(root, "id", f"{base}/opds/catalog")
    _sub(root, "updated", "2026-01-01T00:00:00Z")
    for row in list_registered_items():
        item_id = str(row.get("id") or "")
        if not item_id:
            continue
        title = str(row.get("title") or "Book")
        authors = str(row.get("authors") or "").strip()
        fmt = str(row.get("format") or "epub").lower()
        entry = _sub(root, "entry")
        _sub(entry, "title", title)
        _sub(entry, "id", f"{base}/opds/item/{item_id}")
        if authors:
            author_el = _sub(entry, "author")
            _sub(author_el, "name", authors)
        _sub(
            entry,
            "link",
            attrib={
                "rel": "http://opds-spec.org/acquisition",
                "type": _mime(fmt),
                "href": f"{base}/opds/content/{item_id}",
            },
        )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _mime(fmt: str) -> str:
    return {
        "epub": "application/epub+zip",
        "pdf": "application/pdf",
        "mobi": "application/x-mobipocket-ebook",
        "azw3": "application/vnd.amazon.mobi8-ebook",
        "txt": "text/plain",
        "md": "text/markdown",
        "html": "text/html",
        "fb2": "application/x-fictionbook+xml",
        "djvu": "image/vnd.djvu",
        "chm": "application/vnd.ms-htmlhelp",
        "rtf": "application/rtf",
        "lit": "application/x-ms-reader",
        "cbz": "application/vnd.comicbook+zip",
        "cbr": "application/vnd.comicbook-rar",
        "cb7": "application/x-7z-compressed",
    }.get(fmt, "application/octet-stream")