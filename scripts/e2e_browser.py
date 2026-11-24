#!/usr/bin/env python3
"""Optional Playwright smoke: login → Sniff → Kennel (mock IRC). Requires: pip install playwright && playwright install chromium."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install: pip install playwright && playwright install chromium", file=sys.stderr)
        return 2

    env = {
        **os.environ,
        "BOOKPUP_IRC_MOCK": "1",
        "BOOKPUP_XDCC_MOCK": "1",
    }
    with tempfile.TemporaryDirectory() as td:
        cfg = Path(td) / "cfg"
        cfg.mkdir()
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        (cfg / "config.json").write_text(
            json.dumps(
                {
                    "username": "e2e",
                    "password": "e2e-secret",
                    "irc_server": "h",
                    "irc_port": 6667,
                    "port": port,
                    "host": "127.0.0.1",
                }
            )
        )
        env["HOME"] = td
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "bookpup.py")],
            cwd=ROOT,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 30
        ok = False
        while time.time() < deadline:
            try:
                import urllib.request

                with urllib.request.urlopen(base + "/api/health", timeout=2) as resp:
                    ok = resp.status == 200
                if ok:
                    break
            except OSError:
                time.sleep(0.25)
        if not ok:
            proc.kill()
            err = proc.stderr.read().decode() if proc.stderr else ""
            print("BookPup failed to start", err, file=sys.stderr)
            return 1

        fails = 0
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 390, "height": 844})
                page.goto(base + "/", wait_until="networkidle")
                page.fill("#login-user", "e2e")
                page.fill("#login-pass", "e2e-secret")
                page.click("#login-submit")
                page.wait_for_selector("#app-shell:not(.hidden)", timeout=15000)

                page.click("#tab-search")
                page.wait_for_selector("#search-form", timeout=5000)

                page.click("#tab-library")
                page.wait_for_selector("#lib-items-calibre", timeout=10000)
                browser.close()
        except Exception as exc:
            print(f"[FAIL] browser flow: {exc}", file=sys.stderr)
            fails += 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

        if fails:
            return 1
        print("[PASS] e2e_browser login → sniff → kennel")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())