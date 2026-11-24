"""Validate path segment IDs (staging, usernames) — stdlib only."""

from __future__ import annotations

import re

import os
from pathlib import Path

_USERNAME_RE = re.compile(r"^[\w@+.-]+$", re.ASCII)


def validate_path_segment(value: str, *, label: str = "id") -> str:
    """Reject traversal and separators; return stripped segment."""
    s = str(value or "").strip()
    if not s:
        raise ValueError(f"Invalid {label}")
    if s in (".", ".."):
        raise ValueError(f"Invalid {label}")
    if "/" in s or "\\" in s or "\0" in s:
        raise ValueError(f"Invalid {label}")
    if ".." in s:
        raise ValueError(f"Invalid {label}")
    return s


def validate_username(name: str) -> str:
    s = validate_path_segment(name, label="username")
    if len(s) > 64:
        raise ValueError("Invalid username")
    if not _USERNAME_RE.fullmatch(s):
        raise ValueError(
            "Invalid username (use letters, numbers, and @ . + - _ only)"
        )
    return s


def path_under(base: Path, *parts: str) -> Path:
    """Join parts under base; raise if resolved path escapes base."""
    base = base.resolve()
    target = base.joinpath(*parts).resolve()
    try:
        common = os.path.commonpath([str(base), str(target)])
    except ValueError:
        raise ValueError("Path escapes storage root") from None
    if os.path.normcase(common) != os.path.normcase(str(base)):
        raise ValueError("Path escapes storage root")
    return target