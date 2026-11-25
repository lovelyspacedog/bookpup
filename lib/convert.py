"""Prepare library items for in-browser viewing (MOBI/AZW → EPUB via Calibre)."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import core
from .calibre_convert import calibre_to_epub
from .library import item_path, list_items
from .mobi_convert import mobi_to_epub

VIEW_NATIVE = frozenset({"epub", "pdf", "txt", "cbz", "cbr", "cb7", "md", "html"})
VIEW_MOBILE_CONVERT = frozenset({"mobi", "azw3", "azw", "prc"})
VIEW_CALIBRE_CONVERT = frozenset({"fb2", "lit", "chm", "rtf", "djvu"})
MOBI_DERIVED_VERSION = 3


def _derived_dir() -> Path:
    from . import user_paths

    d = user_paths.derived_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _find_ebook_convert() -> str | None:
    cfg = core.load_config()
    override = cfg.get("ebook_convert_bin") or os.environ.get("BOOKPUP_EBOOK_CONVERT")
    if override and Path(override).is_file():
        return str(Path(override).resolve())
    home = Path.home()
    for cand in (
        home / "calibre-bundle" / "ebook-convert",
        home / "calibre" / "ebook-convert",
        Path("/usr/bin/ebook-convert"),
    ):
        if cand.is_file():
            return str(cand)
    return shutil.which("ebook-convert")


def _ensure_calibre_epub(src: Path, tmp: Path, *, label: str) -> None:
    exe = _find_ebook_convert()
    if not exe:
        raise ValueError(
            f"Calibre is required to read {label} files "
            "(scripts/install_calibre.sh on the server)."
        )
    try:
        calibre_to_epub(exe, src, tmp)
    except Exception as cal_err:
        cal_msg = str(cal_err)
        if hasattr(cal_err, "stderr") and cal_err.stderr:
            cal_msg = str(cal_err.stderr)[:400]
        raise ValueError(f"Conversion failed ({label}): {cal_msg}") from cal_err


def item_format(item_id: str) -> str:
    from .library import _norm_format

    for row in list_items():
        if row.get("id") == item_id:
            return _norm_format(str(row.get("format") or ""))
    raise KeyError(item_id)


def delete_derived(item_id: str) -> None:
    out = _derived_dir() / f"{item_id}.epub"
    if out.is_file():
        out.unlink()


def prepare_view(item_id: str) -> dict:
    """Return view metadata and ensure readable file exists."""
    fmt = item_format(item_id)
    src = item_path(item_id)
    if fmt in VIEW_NATIVE:
        return {
            "format": fmt,
            "path": str(src),
            "converted": False,
        }
    if fmt in VIEW_CALIBRE_CONVERT:
        out = _derived_dir() / f"{item_id}.epub"
        if not out.is_file() or out.stat().st_mtime < src.stat().st_mtime:
            tmp = out.with_suffix(".tmp.epub")
            if tmp.is_file():
                tmp.unlink()
            _ensure_calibre_epub(src, tmp, label=fmt.upper())
            tmp.replace(out)
        return {
            "format": "epub",
            "path": str(out),
            "converted": True,
            "source_format": fmt,
        }
    if fmt in VIEW_MOBILE_CONVERT:
        out = _derived_dir() / f"{item_id}.epub"
        stamp = out.with_suffix(".epub.version")
        stale_stamp = True
        if stamp.is_file():
            try:
                stale_stamp = int(stamp.read_text().strip()) < MOBI_DERIVED_VERSION
            except (OSError, ValueError):
                stale_stamp = True
        if not out.is_file() or out.stat().st_mtime < src.stat().st_mtime or stale_stamp:
            tmp = out.with_suffix(".tmp.epub")
            if tmp.is_file():
                tmp.unlink()
            try:
                mobi_to_epub(src, tmp)
            except Exception as mobi_err:
                exe = _find_ebook_convert()
                if not exe:
                    raise ValueError(
                        f"Conversion failed: {mobi_err}. "
                        "Calibre not installed for fallback (scripts/install_calibre.sh)."
                    ) from mobi_err
                try:
                    calibre_to_epub(exe, src, tmp)
                except Exception as cal_err:
                    cal_msg = str(cal_err)
                    if hasattr(cal_err, "stderr") and cal_err.stderr:
                        cal_msg = str(cal_err.stderr)[:400]
                    raise ValueError(
                        f"Conversion failed: mobi: {mobi_err}; calibre: {cal_msg}"
                    ) from cal_err
            tmp.replace(out)
            stamp.write_text(str(MOBI_DERIVED_VERSION))
        return {
            "format": "epub",
            "path": str(out),
            "converted": True,
            "source_format": fmt,
        }
    raise ValueError(f"Unsupported format for reading: {fmt or 'unknown'}")