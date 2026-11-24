"""Canonical Walk the Trail step order — keep in sync with static/app-walk-trail.js `steps`."""

from __future__ import annotations

WALK_TRAIL_STEP_IDS: tuple[str, ...] = (
    "welcome",
    "query",
    "channel",
    "sniff",
    "den",
    "filter",
    "fetch",
    "queue",
    "kennel",
    "tag",
    "catalog",
    "pack",
    "pack-house",
    "pack-bots",
    "cleanup",
    "done",
)