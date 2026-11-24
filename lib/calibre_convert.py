"""Calibre ebook-convert wrapper with headless Qt env + bundled EGL libs."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _calibre_env(exe: str) -> dict[str, str]:
    env = os.environ.copy()
    bundle = Path(exe).resolve().parent
    lib = bundle / "lib"
    parts = [str(lib)]
    extra = os.environ.get("LD_LIBRARY_PATH", "")
    if extra:
        parts.append(extra)
    env["LD_LIBRARY_PATH"] = os.pathsep.join(parts)
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["QT_QUICK_BACKEND"] = "software"
    env["CALIBRE_CONFIG_DIRECTORY"] = str(Path.home() / ".config" / "bookpup" / "calibre-tmp")
    Path(env["CALIBRE_CONFIG_DIRECTORY"]).mkdir(parents=True, exist_ok=True)
    return env


def calibre_to_epub(exe: str, src: Path, dest: Path, *, timeout: int = 600) -> None:
    tmp = dest.with_suffix(".tmp.epub")
    if tmp.is_file():
        tmp.unlink()
    subprocess.run(
        [exe, str(src), str(tmp)],
        check=True,
        capture_output=True,
        timeout=timeout,
        text=True,
        env=_calibre_env(exe),
    )
    tmp.replace(dest)