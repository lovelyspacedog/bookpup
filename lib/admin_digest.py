"""Household admin overview (quota, jobs, IRC)."""

from __future__ import annotations

import time

from . import accounts
from . import jobs
from . import quota
from . import walk_trail
from .irc_worker import worker


def build_digest() -> dict:
    now = time.time()
    window = now - 7 * 86400
    pups = []
    for row in accounts.list_users():
        u = str(row.get("username") or "")
        if not u:
            continue
        usage = quota.library_usage_for(u)
        q = int(usage.get("quota_bytes") or 1)
        used = int(usage.get("used_bytes") or 0)
        pct = round(100.0 * used / q, 1) if q else 0.0
        wt = accounts.walk_trail_completed_at(u)
        pups.append(
            {
                "username": u,
                "used_bytes": used,
                "quota_bytes": q,
                "used_percent": pct,
                "admin": bool(row.get("admin")),
                "enabled": bool(row.get("enabled", True)),
                "walk_trail_complete": wt is not None,
            }
        )
    recent: list[dict] = []
    failed = 0
    active = 0
    for job in jobs.list_jobs():
        created = float(job.get("created_at") or 0)
        st = str(job.get("state") or "")
        if st in ("error", "cancelled"):
            failed += 1
        if st in ("queued", "running"):
            active += 1
        if created < window:
            continue
        recent.append(
            {
                "id": job.get("id"),
                "type": job.get("type"),
                "state": st,
                "owner": job.get("owner"),
                "title": job.get("title") or job.get("query"),
                "created_at": created,
                "error": (job.get("error") or "")[:120] or None,
            }
        )
    recent.sort(key=lambda j: j.get("created_at") or 0, reverse=True)
    recent = recent[:40]
    health = worker.health_snapshot()
    return {
        "generated_at": now,
        "pups": pups,
        "jobs": {
            "active": active,
            "failed_or_cancelled": failed,
            "recent_7d": recent,
        },
        "irc": health,
        "walk_trail": walk_trail.digest_walk_trail(),
    }