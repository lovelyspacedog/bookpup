#!/usr/bin/env python3
"""Phase 0: join #ebooks, @search, receive txt.zip, print sample lines."""

from __future__ import annotations

import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib.irc_client import IrcSession  # noqa: E402
from lib.search_results import parse_results_zip  # noqa: E402


def main() -> int:
    notices: list[str] = []
    session = IrcSession("irc.irchighway.net", 6667)
    session.on_notice = notices.append
    print(f"nick={session.nick}", flush=True)
    session.connect()
    try:
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            path = tmp.name
        print("@search test (short query)...", flush=True)
        session.search_and_download_results("#ebooks", "test", path)
        print(f"DCC ok: {path} ({Path(path).stat().st_size} bytes)", flush=True)
        rows = parse_results_zip(path)
        for row in rows[:5]:
            print(row.display, flush=True)
        print(f"total_matches={len(rows)}", flush=True)
        return 0 if rows else 1
    except Exception as exc:
        print(f"FAIL: {exc}", flush=True)
        if notices:
            print("notices:", *notices[-5:], sep="\n", flush=True)
        return 2
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())