"""Extract plain text from EPUB spine items and TXT windows (stdlib only)."""

from __future__ import annotations

import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

MIN_EXCERPT_CHARS = 80


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style"):
            self._skip = True
        elif tag in ("p", "br", "div", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip and data:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def normalize_whitespace(text: str) -> str:
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def truncate_for_model(text: str, max_chars: int) -> str:
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def html_to_text(html: bytes | str) -> str:
    if isinstance(html, bytes):
        html = html.decode("utf-8", errors="replace")
    parser = _HTMLText()
    parser.feed(html)
    parser.close()
    return normalize_whitespace(parser.text())


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _opf_root(epub_path: Path) -> tuple[zipfile.ZipFile, ET.Element, dict[str, str], list[str]]:
    zf = zipfile.ZipFile(epub_path)
    container_xml = zf.read("META-INF/container.xml")
    container = ET.fromstring(container_xml)
    rootfile = None
    for el in container.iter():
        if _local(el.tag) == "rootfile":
            rootfile = el.attrib.get("full-path") or el.attrib.get("fullPath")
            break
    if not rootfile:
        zf.close()
        raise ValueError("EPUB container missing rootfile")
    opf_xml = zf.read(rootfile)
    opf = ET.fromstring(opf_xml)
    base_dir = "/".join(rootfile.split("/")[:-1])
    if base_dir:
        base_dir += "/"

    manifest: dict[str, str] = {}
    spine: list[str] = []
    for el in opf.iter():
        tag = _local(el.tag)
        if tag == "item":
            iid = el.attrib.get("id")
            href = el.attrib.get("href")
            if iid and href:
                manifest[iid] = base_dir + href
        elif tag == "itemref":
            idref = el.attrib.get("idref")
            if idref:
                spine.append(idref)
    if not spine:
        zf.close()
        raise ValueError("EPUB spine empty")
    return zf, opf, manifest, spine


def spine_href(manifest: dict[str, str], spine: list[str], spine_index: int | None, href: str | None) -> tuple[int, str]:
    if href:
        href_norm = href.split("#")[0]
        for idx, idref in enumerate(spine):
            mh = manifest.get(idref)
            if mh and (mh == href_norm or mh.endswith("/" + href_norm) or mh.endswith(href_norm)):
                return idx, mh
        return -1, href_norm
    if spine_index is None:
        raise ValueError("spine_index or href required")
    idx = int(spine_index)
    if idx < 0 or idx >= len(spine):
        raise ValueError("spine_index out of range")
    idref = spine[idx]
    mh = manifest.get(idref)
    if not mh:
        raise ValueError("spine item not in manifest")
    return idx, mh


def chapter_key(fmt: str, spine_index: int | None, href: str | None, offset: int | None) -> str:
    if fmt == "epub":
        if href:
            return f"epub:href:{href.split('#')[0]}"
        return f"epub:spine:{spine_index if spine_index is not None else 0}"
    if fmt == "txt":
        base = int(offset or 0)
        window = (base // 12000) * 12000
        return f"txt:window:{window}"
    return f"{fmt}:unknown"


def extract_epub_chapter(
    epub_path: Path,
    *,
    spine_index: int | None = None,
    href: str | None = None,
    max_chars: int = 8000,
) -> tuple[str, str, int]:
    zf, _opf, manifest, spine = _opf_root(epub_path)
    try:
        idx, item_href = spine_href(manifest, spine, spine_index, href)
        key = chapter_key("epub", idx if idx >= 0 else spine_index, item_href, None)
        try:
            raw = zf.read(item_href)
        except KeyError:
            # try path variants
            alt = item_href.lstrip("/")
            raw = zf.read(alt)
        text = truncate_for_model(html_to_text(raw), max_chars)
        return key, text, len(text)
    finally:
        zf.close()


def extract_txt_window(
    txt_path: Path,
    *,
    offset: int | None = None,
    window_chars: int = 12000,
    max_chars: int = 8000,
) -> tuple[str, str, int]:
    data = txt_path.read_text(encoding="utf-8", errors="replace")
    length = len(data)
    center = int(offset or 0)
    center = max(0, min(center, length))
    half = max(window_chars // 2, 1000)
    start = max(0, center - half)
    end = min(length, start + window_chars)
    if end - start < window_chars and start > 0:
        start = max(0, end - window_chars)
    snippet = data[start:end]
    key = chapter_key("txt", None, None, start)
    text = truncate_for_model(normalize_whitespace(snippet), max_chars)
    return key, text, len(text)


def extract_excerpt(
    file_path: Path,
    fmt: str,
    *,
    spine_index: int | None = None,
    href: str | None = None,
    offset: int | None = None,
    max_chars: int = 8000,
) -> tuple[str, str, int]:
    fmt = fmt.lower()
    if fmt == "epub":
        return extract_epub_chapter(
            file_path, spine_index=spine_index, href=href, max_chars=max_chars
        )
    if fmt == "txt":
        return extract_txt_window(file_path, offset=offset, max_chars=max_chars)
    raise ValueError(f"AI excerpt not supported for format: {fmt}")