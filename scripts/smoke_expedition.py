#!/usr/bin/env python3
"""API smoke on Expedition (localhost). Does not print passwords."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

BASE = os.environ.get("BOOKPUP_SMOKE_BASE", "http://127.0.0.1:18478")
CONFIG = Path.home() / ".config" / "bookpup" / "config.json"
CSRF = {"X-Bookpup": "1"}


def req(method: str, path: str, body: dict | None = None, headers: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    hdrs = {**CSRF, **(headers or {})}
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    rq = urllib.request.Request(BASE + path, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"error": raw}


def load_login() -> tuple[str, str]:
    cfg = json.loads(CONFIG.read_text())
    return str(cfg["username"]).strip(), str(cfg["password"])


def main() -> int:
    results: dict[str, str] = {}
    fails = 0

    def ok(key: str, cond: bool, detail: str = "") -> None:
        nonlocal fails
        results[key] = "PASS" if cond else f"FAIL {detail}".strip()
        if not cond:
            fails += 1
            print(f"[FAIL] {key}: {detail}", file=sys.stderr)
        else:
            print(f"[PASS] {key}")

    code, health = req("GET", "/api/health")
    ok("health", code == 200 and health.get("ok"), f"code={code}")
    ok(
        "health_liveness_contract",
        health.get("ok") == health.get("config_dir_writable"),
        str(health.get("ok")),
    )

    code, ready = req("GET", "/api/ready")
    ok("ready", code == 200 and "ready" in ready, f"code={code} ready={ready.get('ready')}")

    code, cfg = req("GET", "/api/config")
    pub = cfg.get("koreader_sync_url", "")
    ok("public_url", code == 200 and pub == health.get("public_url"), pub)

    user, password = load_login()

    code, _ = req("POST", "/api/login", {"username": user, "password": "wrong-password-smoke"})
    ok("login_wrong", code == 401, str(code))

    code, login = req("POST", "/api/login", {"username": user, "password": password})
    token = login.get("token") if code == 200 else None
    ok("login_ok", code == 200 and bool(token), str(code))
    if not token:
        print(json.dumps(results, indent=2))
        return 1

    auth = {"Authorization": f"Bearer {token}"}
    code, sess = req("GET", "/api/session", headers=auth)
    ok("session", code == 200 and sess.get("username") == user, str(sess))

    admin = bool(sess.get("admin"))
    ok("admin_flag", admin, str(sess.get("admin")))

    test_user = "smokepup_" + str(int(time.time()))[-6:]
    if admin:
        code, created = req(
            "POST",
            "/api/admin/accounts",
            {"username": test_user, "password": "smoke-temp-9", "quota_gb": 0.1},
            headers=auth,
        )
        ok("admin_create", code in (200, 201), str(created))
        code, _ = req("DELETE", f"/api/admin/accounts/{test_user}", headers=auth)
        ok("admin_remove", code == 200, str(code))
    else:
        results["admin_create"] = "SKIP (not admin)"
        results["admin_remove"] = "SKIP"

    code, search = req(
        "POST",
        "/api/search",
        {"query": "asimov foundation", "channel": "irchighway:ebooks"},
        headers=auth,
    )
    job = search.get("job") or search
    job_id = job.get("id")
    ok("search_queued", code in (200, 201) and bool(job_id), str(search))

    search_done = False
    if job_id:
        deadline = time.time() + 90
        while time.time() < deadline:
            code, st = req("GET", f"/api/jobs/{job_id}", headers=auth)
            state = (st.get("job") or st).get("state")
            if state in ("done", "failed", "cancelled"):
                search_done = state == "done"
                break
            time.sleep(2)
    ok("search_irc", search_done, "timeout or failed job")

    code, lib = req("GET", "/api/library", headers=auth)
    ok("library_list", code == 200 and "items" in lib or "library" in lib, str(code))

    subprocess.run(["pkill", "-f", "/home/tonypup/bookpup/bookpup.py"], check=False, stdout=subprocess.DEVNULL)
    time.sleep(2)
    subprocess.run([str(Path.home() / "bookpup" / "start")], check=True, stdout=subprocess.DEVNULL)
    time.sleep(3)
    code, sess2 = req("GET", "/api/session", headers=auth)
    ok("session_after_restart", code == 200 and sess2.get("username") == user, str(code))

    code, _ = req("POST", "/api/logout", headers=auth)
    ok("logout", code == 200, str(code))

    ai = req("GET", "/api/capabilities")[1]
    ok("capabilities", isinstance(ai, dict), "")
    results["reader_ai"] = "ready" if ai.get("reader_ai") else "disabled"

    today = time.strftime("%Y-%m-%d")
    print(json.dumps({"date": today, "base": BASE, "results": results}, indent=2))
    return fails


if __name__ == "__main__":
    raise SystemExit(main())