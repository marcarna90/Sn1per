"""Render an engagement to machine-readable JSON.

This format is the contract the (upcoming) orchestration layer and any
external tooling consume, so it intentionally exposes the full normalised
model plus the derived metrics.
"""

from __future__ import annotations

import json

from jarvis import branding
from jarvis.report.model import Engagement


def render(engagement: Engagement) -> str:
    payload = {
        "tool": {
            "name": branding.NAME,
            "long_name": branding.LONG_NAME,
            "version": branding.VERSION,
            "engine": branding.ENGINE_CREDIT,
        },
        "engagement": engagement.to_dict(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)
