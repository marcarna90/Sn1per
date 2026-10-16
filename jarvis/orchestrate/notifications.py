"""End-of-campaign notifications.

The summary builder is pure and testable; the Slack sender is a thin,
best-effort wrapper over the stdlib (no third-party SDK) and never raises —
a failed notification must not fail the campaign.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from jarvis import branding
from jarvis.orchestrate.model import CampaignResult


def summarize(result: CampaignResult) -> str:
    """Build a concise, human-readable campaign summary."""
    done = sum(1 for t in result.tasks if t.status == "done")
    skipped = sum(1 for t in result.tasks if t.status == "skipped")
    failed = len(result.failed)
    lines = [
        f"{branding.NAME}: campaign '{result.campaign}' finished "
        f"({'dry-run' if result.dry_run else 'live'})",
        f"workspace: {result.workspace}",
        f"tasks: {len(result.tasks)} total — {done} done, "
        f"{skipped} skipped, {failed} failed",
    ]
    report_paths = [
        f"{fmt}: {path}"
        for fmt, path in result.reports.items()
        if fmt not in ("error", "pdf_error")
    ]
    if report_paths:
        lines.append("reports — " + "; ".join(report_paths))
    return "\n".join(lines)


def send_slack(webhook: str, text: str, timeout: int = 10) -> bool:
    """POST ``text`` to a Slack incoming webhook. Returns success; never raises."""
    if not webhook:
        return False
    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=payload, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError):
        return False
