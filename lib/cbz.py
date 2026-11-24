"""CBZ comic archive pages (ZIP of images)."""

from __future__ import annotations

import zipfile
from pathlib import Path

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"})


def _image_members(zf: zipfile.ZipFile) -> list[str]:
    names: list[str] = []
    for info in zf.infolist():
        if info.is_dir():
            continue
        base = Path(info.filename).name
        if base.startswith("."):
            continue
        if Path(base).suffix.lower() in IMAGE_SUFFIXES:
            names.append(info.filename)
    names.sort(key=lambda n: n.lower())
    return names


def page_count(path: Path) -> int:
    with zipfile.ZipFile(path, "r") as zf:
        return len(_image_members(zf))


def page_bytes(path: Path, index: int) -> tuple[bytes, str]:
    if index < 0:
        raise IndexError("page index out of range")
    with zipfile.ZipFile(path, "r") as zf:
        members = _image_members(zf)
        if index >= len(members):
            raise IndexError("page index out of range")
        name = members[index]
        data = zf.read(name)
        suffix = Path(name).suffix.lower()
        mime = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }.get(suffix, "application/octet-stream")
        return data, mime


def comic_meta(path: Path) -> dict:
    with zipfile.ZipFile(path, "r") as zf:
        pages = len(_image_members(zf))
    return {"format": "cbz", "pages": pages}