"""Headless MOBI/AZW → EPUB via vendored kindleunpack (no Calibre/Qt)."""

from __future__ import annotations

import re
import shutil
import sys
import zipfile
from pathlib import Path

_INLINE_STYLE_FIXES = (
    (re.compile(r"letter-spacing\s*:\s*[^;\"']+;?", re.I), ""),
    (re.compile(r"word-spacing\s*:\s*[^;\"']+;?", re.I), ""),
    (re.compile(r"text-justify\s*:\s*[^;\"']+;?", re.I), ""),
    (re.compile(r"font-variant(?:-[\w-]+)?\s*:\s*small-caps[^;\"']*;?", re.I), ""),
    (re.compile(r"text-align\s*:\s*justify;?", re.I), "text-align:left;"),
)


def _sanitize_mobi7_html(root: Path) -> None:
    """Strip Kindle unpack styles that break nav/title typography in epub.js."""
    for path in root.rglob("*.html"):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        orig = text
        for pattern, repl in _INLINE_STYLE_FIXES:
            text = pattern.sub(repl, text)
        if text != orig:
            path.write_text(text, encoding="utf-8")


def _vendor_path() -> Path:
    return Path(__file__).resolve().parent.parent / "vendor"


_CONTAINER = b"""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""


def _repack_mobi7_to_epub(mobi7_dir: Path, dest: Path) -> None:
    """Zip kindleunpack mobi7/ tree into a minimal EPUB (epub.js can open)."""
    root = mobi7_dir.resolve()
    if not (root / "content.opf").is_file():
        raise ValueError("mobi7 unpack missing content.opf")
    mimetype = b"application/epub+zip"
    with zipfile.ZipFile(dest, "w") as zf:
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, mimetype)
        zf.writestr("META-INF/container.xml", _CONTAINER)
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            arc = "OEBPS/" + path.relative_to(root).as_posix()
            zf.write(path, arc)


def mobi_to_epub(src: Path, dest: Path) -> None:
    vendor = _vendor_path()
    if not vendor.is_dir():
        raise RuntimeError("vendor/ bundle missing (mobi unpacker)")
    vpath = str(vendor)
    if vpath not in sys.path:
        sys.path.insert(0, vpath)
    import mobi  # noqa: WPS433 — vendored

    tempdir, filepath = mobi.extract(str(src))
    try:
        fp = Path(filepath)
        if not fp.is_file():
            raise ValueError("mobi extract did not produce a file")
        suffix = fp.suffix.lower()
        if suffix == ".epub":
            shutil.copy2(fp, dest)
            return
        if suffix in (".html", ".htm"):
            mobi7 = fp.parent
            if mobi7.name != "mobi7":
                mobi7 = Path(tempdir) / "mobi7"
            _sanitize_mobi7_html(mobi7)
            _repack_mobi7_to_epub(mobi7, dest)
            return
        if suffix == ".pdf":
            raise ValueError("Extracted PDF; not supported in EPUB reader")
        shutil.copy2(fp, dest)
    finally:
        shutil.rmtree(tempdir, ignore_errors=True)