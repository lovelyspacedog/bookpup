"""Atomic text/JSON file writes."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def atomic_write_text(path: Path, text: str, *, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def atomic_write_json(path: Path, data: Any, *, indent: int = 2, mode: int = 0o600) -> None:
    text = json.dumps(data, indent=indent) + "\n"
    atomic_write_text(path, text, mode=mode)