"""Delayed Pack chat replies from BugBot / FeatureCat."""

from __future__ import annotations

import os
import random
import threading
import time

from . import pack_chat

CLEAR_COMMAND = "clear"

_REPLY_DELAY_MIN_S = 2.0
_REPLY_DELAY_MAX_S = 5.0


def _reply_delay_seconds() -> float:
    if os.environ.get("BOOKPUP_BOT_REPLY_DELAY", "").strip() == "0":
        return 0.0
    return random.uniform(_REPLY_DELAY_MIN_S, _REPLY_DELAY_MAX_S)


def _deliver(from_bot: str, to_user: str, text: str, *, kind: str, delay: float) -> None:
    if delay > 0:
        time.sleep(delay)
    pack_chat.append_virtual_dm(from_bot, to_user, text, kind=kind)


def is_clear_command(text: str) -> bool:
    return pack_chat.sanitize_message(text).lower() == CLEAR_COMMAND


def schedule_delayed_virtual_dm(
    from_bot: str, to_user: str, text: str, *, kind: str
) -> None:
    delay = _reply_delay_seconds()
    if delay <= 0:
        pack_chat.append_virtual_dm(from_bot, to_user, text, kind=kind)
        return
    threading.Thread(
        target=_deliver,
        args=(from_bot, to_user, text),
        kwargs={"kind": kind, "delay": delay},
        name="bookpup-bot-reply",
        daemon=True,
    ).start()