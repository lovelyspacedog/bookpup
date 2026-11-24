"""Dispatch comic archive helpers by file extension."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

from . import cb7 as cb7_mod
from . import cbz as cbz_mod
from . import cbr as cbr_mod


def comic_module(path: Path) -> ModuleType:
    ext = path.suffix.lower()
    if ext == ".cbr":
        return cbr_mod
    if ext == ".cbz":
        return cbz_mod
    if ext == ".cb7":
        return cb7_mod
    raise ValueError(f"Not a comic archive: {ext or path.name}")