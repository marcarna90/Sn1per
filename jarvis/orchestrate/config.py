"""Load and validate a campaign file (JSON natively, YAML when available)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jarvis.orchestrate.model import Campaign, Phase, ReportSpec


class CampaignError(ValueError):
    """Raised for malformed or unreadable campaign files."""


def _slug(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip("-")
    return safe.lower() or "campaign"


def _load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise CampaignError(
                "YAML campaign files require PyYAML ('pip install pyyaml'). "
                "Alternatively, use a JSON campaign file (no dependency needed)."
            ) from exc
        data = yaml.safe_load(text)
    else:
        # Default to JSON for .json and anything else.
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise CampaignError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise CampaignError("Campaign file must contain a top-level object/mapping.")
    return data


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    raise CampaignError(f"Expected a string or list, got {type(value).__name__}.")


def parse_campaign(data: dict[str, Any]) -> Campaign:
    name = str(data.get("campaign") or data.get("name") or "").strip()
    if not name:
        raise CampaignError("Campaign file must set 'campaign' (the engagement name).")

    targets = _as_list(data.get("targets"))

    raw_workflow = data.get("workflow")
    if not isinstance(raw_workflow, list) or not raw_workflow:
        raise CampaignError("'workflow' must be a non-empty list of phases.")

    phases: list[Phase] = []
    for i, raw in enumerate(raw_workflow):
        if isinstance(raw, str):
            raw = {"mode": raw}
        if not isinstance(raw, dict):
            raise CampaignError(f"workflow[{i}] must be a string or object.")
        try:
            phases.append(
                Phase(
                    mode=str(raw.get("mode", "")).strip(),
                    targets=_as_list(raw.get("targets")),
                    options=dict(raw.get("options") or {}),
                    parallel=int(raw.get("parallel", 1)),
                )
            )
        except (ValueError, TypeError) as exc:
            raise CampaignError(f"workflow[{i}]: {exc}") from exc

    report_raw = data.get("report") or {}
    if not isinstance(report_raw, dict):
        raise CampaignError("'report' must be an object.")
    report = ReportSpec(
        formats=_as_list(report_raw.get("formats")) or ["html", "md", "json"],
        name=str(report_raw.get("name", "")).strip(),
        client=str(report_raw.get("client", "")).strip(),
        logo=str(report_raw.get("logo", "")).strip(),
    )

    workspace = str(data.get("workspace") or "").strip() or _slug(name)

    try:
        return Campaign(
            name=name,
            targets=targets,
            workflow=phases,
            workspace=workspace,
            report=report,
        )
    except ValueError as exc:
        raise CampaignError(str(exc)) from exc


def load_campaign(path: str) -> Campaign:
    p = Path(path).expanduser()
    if not p.is_file():
        raise CampaignError(f"Campaign file not found: {p}")
    return parse_campaign(_load_raw(p))
