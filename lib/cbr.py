"""CBR comic archive pages (RAR of images) via 7z then unrar."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .cbz import IMAGE_SUFFIXES
from .comic_errors import ComicReadError

_LIST_LINE = re.compile(r"^\S+\s+\S+\s+\S+\s+\d+\s+\d+\s+(.*)$")
_TOOL_TIMEOUT = 120


def _decode(chunk: bytes) -> str:
    return chunk.decode("utf-8", errors="replace")


def _filter_images(names: list[str]) -> list[str]:
    out: list[str] = []
    for raw in names:
        name = raw.replace("\\", "/").strip()
        if not name:
            continue
        base = Path(name).name
        if base.startswith("."):
            continue
        if Path(base).suffix.lower() in IMAGE_SUFFIXES:
            out.append(name)
    out.sort(key=lambda n: n.lower())
    return out


def _mime_for_name(name: str) -> str:
    suffix = Path(name).suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(suffix, "application/octet-stream")


def _tool_debug(label: str, proc: subprocess.CompletedProcess) -> str:
    return (
        f"=== {label} (exit {proc.returncode}) ===\n"
        + _decode(proc.stdout)
        + _decode(proc.stderr)
    )


def _list_7z(path: Path) -> tuple[list[str] | None, str]:
    if not shutil.which("7z"):
        return None, "=== 7z ===\n(not installed)\n"
    proc = subprocess.run(
        ["7z", "l", "-ba", str(path)],
        capture_output=True,
        timeout=_TOOL_TIMEOUT,
    )
    debug = _tool_debug("7z l -ba", proc)
    if proc.returncode != 0:
        return None, debug
    names: list[str] = []
    for line in _decode(proc.stdout).splitlines():
        line = line.rstrip()
        if not line:
            continue
        m = _LIST_LINE.match(line)
        if m:
            names.append(m.group(1))
    images = _filter_images(names)
    return (images if images else None), debug


def _list_unrar(path: Path) -> tuple[list[str] | None, str]:
    if not shutil.which("unrar"):
        return None, "=== unrar ===\n(not installed)\n"
    proc = subprocess.run(
        ["unrar", "lb", str(path)],
        capture_output=True,
        timeout=_TOOL_TIMEOUT,
    )
    debug = _tool_debug("unrar lb", proc)
    if proc.returncode != 0:
        return None, debug
    names = [ln.strip() for ln in _decode(proc.stdout).splitlines() if ln.strip()]
    images = _filter_images(names)
    return (images if images else None), debug


def _list_members(path: Path) -> list[str]:
    debug_parts: list[str] = []
    for list_fn in (_list_7z, _list_unrar):
        members, dbg = list_fn(path)
        debug_parts.append(dbg)
        if members:
            return members
    raise ComicReadError(
        "Couldn't read this CBR (encrypted, damaged, or unsupported RAR).",
        debug_stderr="\n\n".join(debug_parts),
    )


def _extract_7z(path: Path, member: str) -> tuple[bytes | None, str]:
    if not shutil.which("7z"):
        return None, "=== 7z e -so ===\n(not installed)\n"
    proc = subprocess.run(
        ["7z", "e", "-so", str(path), member],
        capture_output=True,
        timeout=_TOOL_TIMEOUT,
    )
    debug = _tool_debug(f"7z e -so {member}", proc)
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout, debug
    return None, debug


def _extract_unrar(path: Path, member: str) -> tuple[bytes | None, str]:
    if not shutil.which("unrar"):
        return None, "=== unrar p ===\n(not installed)\n"
    proc = subprocess.run(
        ["unrar", "p", "-inul", str(path), member],
        capture_output=True,
        timeout=_TOOL_TIMEOUT,
    )
    debug = _tool_debug(f"unrar p {member}", proc)
    if proc.returncode == 0 and proc.stdout:
        return proc.stdout, debug
    return None, debug


def _extract_member(path: Path, member: str) -> bytes:
    debug_parts: list[str] = []
    for extract_fn in (_extract_7z, _extract_unrar):
        data, dbg = extract_fn(path, member)
        debug_parts.append(dbg)
        if data is not None:
            return data
    raise ComicReadError(
        f"Couldn't extract comic page: {member}",
        debug_stderr="\n\n".join(debug_parts),
    )


def page_count(path: Path) -> int:
    return len(_list_members(path))


def page_bytes(path: Path, index: int) -> tuple[bytes, str]:
    if index < 0:
        raise IndexError("page index out of range")
    members = _list_members(path)
    if index >= len(members):
        raise IndexError("page index out of range")
    name = members[index]
    data = _extract_member(path, name)
    return data, _mime_for_name(name)


def comic_meta(path: Path) -> dict:
    pages = len(_list_members(path))
    return {"format": "cbr", "pages": pages}