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

from jarvis.orchestrate.commands import build_sniper_command, is_file_based
from jarvis.orchestrate.executor import Executor
from jarvis.orchestrate.model import Campaign, CampaignResult, Task, TaskResult

ProgressFn = Callable[[TaskResult], None]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def plan(
    campaign: Campaign,
    sniper_bin: str = "sniper",
    workspace_dir: str | None = None,
) -> list[list[Task]]:
    """Expand the campaign into a list of per-phase task batches.

    ``workspace_dir`` fixes where a file-based mode's ``-f`` targets file
    lives; when omitted a path derived from the workspace alias is used so a
    dry-run still shows a meaningful command.
    """
    ws_base = Path(workspace_dir) if workspace_dir else Path(campaign.workspace)
    batches: list[list[Task]] = []
    for phase_index, phase in enumerate(campaign.workflow):
        targets = phase.targets or campaign.targets
        file_based = is_file_based(phase.mode, phase.options.get("file_targets"))

        if file_based:
            targets_file = str(
                ws_base / "scans" / f"jarvis-targets-p{phase_index}-{phase.mode}.txt"
            )
            command = build_sniper_command(
                target="",
                mode=phase.mode,
                workspace=campaign.workspace,
                options=phase.options,
                sniper_bin=sniper_bin,
                targets_file=targets_file,
            )
            batches.append(
                [
                    Task(
                        id=f"p{phase_index}-{phase.mode}-file",
                        phase_index=phase_index,
                        mode=phase.mode,
                        target=f"@{len(targets)} targets",
                        workspace=campaign.workspace,
                        options=phase.options,
                        command=command,
                        targets_file=targets_file,
                        file_targets=list(targets),
                    )
                ]
            )
            continue

        batch: list[Task] = []
        for target in targets:
            command = build_sniper_command(
                target=target,
                mode=phase.mode,
                workspace=campaign.workspace,
                options=phase.options,
                sniper_bin=sniper_bin,
            )
            batch.append(
                Task(
                    id=f"p{phase_index}-{phase.mode}-{target}",
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


def _load_done_ids(ws_dir: Path | None) -> set[str]:
    """Task ids already completed in a prior run (for --resume)."""
    if ws_dir is None:
        return set()
    state = ws_dir / "scans" / "jarvis-campaign-state.json"
    try:
        data = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()
    done = set()
    for t in data.get("tasks", []):
        if t.get("status") in ("done", "skipped"):
            tid = (t.get("task") or {}).get("id") or t.get("id")
            if tid:
                done.add(tid)
    return done


def _write_targets_file(task: Task, write_enabled: bool) -> None:
    if not write_enabled or not task.targets_file or not task.file_targets:
        return
    path = Path(task.targets_file)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(task.file_targets) + "\n", encoding="utf-8")
    except OSError:
        pass


def run_campaign(
    campaign: Campaign,
    executor: Executor,
    workspace_dir: str | None = None,
    generate_report: bool = True,
    sniper_bin: str = "sniper",
    progress: ProgressFn | None = None,
    resume: bool = False,
) -> CampaignResult:
    ws_dir = Path(workspace_dir).expanduser() if workspace_dir else None
    write_enabled = not executor.dry_run and ws_dir is not None
    result = CampaignResult(
        campaign=campaign.name,
        workspace=campaign.workspace,
        started_at=_now(),
        dry_run=executor.dry_run,
    )

    done_ids = _load_done_ids(ws_dir) if (resume and not executor.dry_run) else set()

    batches = plan(campaign, sniper_bin=sniper_bin, workspace_dir=workspace_dir)
    for batch in batches:
        if not batch:
            continue
        phase = campaign.workflow[batch[0].phase_index]

        pending: list[Task] = []
        for task in batch:
            if task.id in done_ids:
                skipped = TaskResult(
                    task=task, status="skipped", note="already done (resume)"
                )
                result.tasks.append(skipped)
                if progress:
                    progress(skipped)
            else:
                _write_targets_file(task, write_enabled)
                pending.append(task)

        if pending:
            workers = max(1, min(phase.parallel, len(pending)))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for task_result in pool.map(executor.execute, pending):
                    result.tasks.append(task_result)
                    if progress:
                        progress(task_result)
        if write_enabled:
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
    if write_enabled:
        _checkpoint(ws_dir, result)
    return result
