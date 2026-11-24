"""Create download jobs from search result rows."""

from __future__ import annotations

from typing import Any

from . import jobs
from . import irc_targets
from . import job_download
from . import soulseek_limits
from .irc_commands import resolve_download_command
from .irc_worker import worker

BATCH_MAX = 5


def create_download_from_search(
    parent: dict,
    *,
    command: str,
    title: str | None,
    irc_target: str | None,
    owner: str,
    validated_channel,
    row: dict[str, Any] | None = None,
    xdcc: dict[str, Any] | None = None,
    soulseek: dict[str, Any] | None = None,
) -> dict:
    parent_channel = validated_channel(parent.get("channel"))
    row_target = irc_target
    if parent_channel == irc_targets.SEARCH_ALL_ID:
        if not row_target:
            raise ValueError("irc_target required for all-network search results")
        channel = validated_channel(row_target)
    else:
        channel = parent_channel

    soulseek_blob = soulseek
    if soulseek_blob is None and isinstance(row, dict):
        if job_download.row_is_soulseek(row):
            soulseek_blob = job_download.validate_soulseek_row(row)
            channel = irc_targets.SOULSEEK_INDEX_ID

    if soulseek_blob:
        soulseek_limits.assert_download_allowed(owner)
        soulseek_limits.record_download(owner)
        cmd = command if command.strip() else "soulseek"
        job = jobs.create_job(
            "download",
            command=cmd,
            channel=channel,
            title=title,
            parent_id=str(parent.get("id") or ""),
            owner=owner,
            download_kind="soulseek",
            soulseek=soulseek_blob,
        )
        worker.enqueue(job["id"])
        return job

    xdcc_blob = xdcc
    if xdcc_blob is None and isinstance(row, dict):
        if job_download.row_is_xdcc(row):
            xdcc_blob = job_download.validate_xdcc_row(row)
            channel = validated_channel(str(row.get("irc_target") or parent_channel))

    all_results = parent.get("results") if isinstance(parent.get("results"), list) else []
    results = list(all_results)
    if parent_channel == irc_targets.SEARCH_ALL_ID:
        results = [r for r in results if str(r.get("irc_target") or "") == channel]

    if xdcc_blob:
        irc_cmd = command if command.strip() else f"!xdcc #{xdcc_blob['slot']}"
        fields: dict[str, Any] = {"xdcc": xdcc_blob}
        job = jobs.create_job(
            "download",
            command=irc_cmd,
            channel=channel,
            title=title,
            parent_id=str(parent.get("id") or ""),
            owner=owner,
            download_kind="xdcc",
            **fields,
        )
        worker.enqueue(job["id"])
        return job

    irc_cmd, rewrite_hint, redirect = resolve_download_command(
        channel,
        command,
        title=title,
        search_results=results,
        all_search_results=all_results if parent_channel == irc_targets.SEARCH_ALL_ID else None,
    )
    if redirect:
        channel = validated_channel(redirect)
    fields = {}
    if irc_cmd != command:
        fields["command_original"] = command
    if redirect:
        fields["fetch_redirect_target"] = redirect
    if rewrite_hint:
        fields["command_rewrite_hint"] = rewrite_hint
    job = jobs.create_job(
        "download",
        command=irc_cmd,
        channel=channel,
        title=title,
        parent_id=str(parent.get("id") or ""),
        owner=owner,
        **fields,
    )
    worker.enqueue(job["id"])
    return job