#!/usr/bin/env python3
"""Deprecated alias — use scripts/smoke_production.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    prod = Path(__file__).resolve().parent / "smoke_production.py"
    raise SystemExit(subprocess.call([sys.executable, str(prod), *sys.argv[1:]]))