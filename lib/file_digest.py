"""KOReader-compatible document IDs (filename MD5 + partial content MD5)."""

from __future__ import annotations

import hashlib
from pathlib import Path


def partial_md5(path: Path) -> str:
    """Sampled MD5 used by KOReader *partial_md5_checksum* mode."""
    digest = hashlib.md5()
    step = 1024
    size = 1024
    with path.open("rb") as handle:
        for i in range(-1, 11):
            offset = int(step * (4**i))
            handle.seek(offset)
            chunk = handle.read(size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def filename_md5(filename: str) -> str:
    base = Path(filename).name
    return hashlib.md5(base.encode("utf-8")).hexdigest()