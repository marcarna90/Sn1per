"""Expand a campaign into tasks and execute them phase by phase.

Phases run **sequentially** (recon before web scans before vuln scans);
tasks **within** a phase run concurrently up to that phase's ``parallel``
limit. State is checkpointed to the workspace after every phase so an
interrupted campaign leaves a readable record of what ran.
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from jarvis.orchestrate.commands import build_sniper_command
from jarvis.orchestrate.executor import Executor
from jarvis.orchestrate.model import Campaign, CampaignResult, Task, TaskResult

ProgressFn = Callable[[TaskResult], None]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def plan(campaign: Campaign, sniper_bin: str = "sniper") -> list[list[Task]]:
    """Expand the campaign into a list of per-phase task batches."""
    batches: list[list[Task]] = []
    for phase_index, phase in enumerate(campaign.workflow):
        targets = phase.targets or campaign.targets
        batch: list[Task] = []
        for target in targets:
            task_id = f"p{phase_index}-{phase.mode}-{target}"
            command = build_sniper_command(
                target=target,
                mode=phase.mode,
                workspace=campaign.workspace,
                options=phase.options,
                sniper_bin=sniper_bin,
            )
            batch.append(
                Task(
                    id=task_id,
                    phase_index=phase_index,
                    mode=phase.mode,
                    target=target,
                    workspace=campaign.workspace,
                    options=phase.options,
                    command=command,
                )
            )
        batches.append(batch)
    return batches


def _checkpoint(workspace_dir: Path | None, result: CampaignResult) -> None:
    if workspace_dir is None:
        return
    scans = workspace_dir / "scans"
    try:
        scans.mkdir(parents=True, exist_ok=True)
        (scans / "jarvis-campaign-state.json").write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError:
        pass  # state is a convenience, never fatal


def run_campaign(
    campaign: Campaign,
    executor: Executor,
    workspace_dir: str | None = None,
    generate_report: bool = True,
    sniper_bin: str = "sniper",
    progress: ProgressFn | None = None,
) -> CampaignResult:
    ws_dir = Path(workspace_dir).expanduser() if workspace_dir else None
    result = CampaignResult(
        campaign=campaign.name,
        workspace=campaign.workspace,
        started_at=_now(),
        dry_run=executor.dry_run,
    )

    batches = plan(campaign, sniper_bin=sniper_bin)
    for batch in batches:
        if not batch:
            continue
        phase = campaign.workflow[batch[0].phase_index]
        workers = max(1, min(phase.parallel, len(batch)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for task_result in pool.map(executor.execute, batch):
                result.tasks.append(task_result)
                if progress:
                    progress(task_result)
        _checkpoint(ws_dir, result)

    # Final consolidated report (real runs only; dry-run has no loot).
    if generate_report and not executor.dry_run and ws_dir and ws_dir.is_dir():
        from jarvis.report.generate import generate_reports

        try:
            result.reports = generate_reports(
                loot_root=ws_dir,
                out_dir=ws_dir / "reports",
                formats=campaign.report.formats,
                name=campaign.report.name or campaign.name,
                client=campaign.report.client,
                logo_path=campaign.report.logo or None,
            )
        except (FileNotFoundError, ValueError) as exc:
            result.reports = {"error": str(exc)}

    result.ended_at = _now()
    _checkpoint(ws_dir, result)
    return result
