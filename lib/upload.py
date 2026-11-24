"""Multipart form uploads (stdlib only)."""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path


def _parse_boundary(content_type: str) -> bytes:
    m = re.search(r"boundary=([^;\s]+)", content_type, re.I)
    if not m:
        raise ValueError("multipart boundary missing")
    return m.group(1).strip().encode("ascii", "ignore")


def save_multipart_files(body_path: Path, content_type: str) -> list[Path]:
    """Extract uploaded files from a spooled multipart body to a temp directory."""
    boundary = _parse_boundary(content_type)
    marker = b"--" + boundary
    end_marker = marker + b"--"
    data = body_path.read_bytes()
    saved: list[Path] = []
    out_dir = Path(tempfile.mkdtemp(prefix="bookpup-upload-"))
    pos = 0
    while True:
        start = data.find(marker, pos)
        if start < 0:
            break
        start += len(marker)
        if data[start : start + 2] == b"--":
            break
        if data[start : start + 2] == b"\r\n":
            start += 2
        hdr_end = data.find(b"\r\n\r\n", start)
        if hdr_end < 0:
            break
        headers = data[start:hdr_end].decode("latin-1", "replace")
        chunk_start = hdr_end + 4
        next_part = data.find(marker, chunk_start)
        if next_part < 0:
            next_part = data.find(end_marker, chunk_start)
        if next_part < 0:
            chunk_end = len(data)
        else:
            chunk_end = next_part
            if data[chunk_end - 2 : chunk_end] == b"\r\n":
                chunk_end -= 2
        fname_m = re.search(r'filename="([^"]+)"', headers, re.I)
        if fname_m:
            name = Path(fname_m.group(1)).name
            if name:
                dest = out_dir / name
                dest.write_bytes(data[chunk_start:chunk_end])
                saved.append(dest)
        pos = next_part if next_part >= 0 else len(data)
    if not saved:
        raise ValueError("No files in upload")
    return saved


def read_multipart_upload(body_path: Path, content_type: str) -> bytes:
    saved = save_multipart_files(body_path, content_type)
    out_dir = saved[0].parent
    try:
        pick = max(saved, key=lambda p: p.stat().st_size)
        return pick.read_bytes()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)