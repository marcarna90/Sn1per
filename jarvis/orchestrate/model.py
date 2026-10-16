"""Data model for campaign orchestration.

A *campaign* is a declarative description of an engagement: a set of targets
and an ordered workflow of *phases*. The planner expands a campaign into
concrete *tasks* (one per target x phase); the runner executes them through a
pluggable executor and records a *result* per task.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Phase:
    """One step of a campaign workflow (maps to a Sn1per mode)."""

    mode: str
    targets: list[str] = field(default_factory=list)  # overrides campaign targets
    options: dict[str, Any] = field(default_factory=dict)
    parallel: int = 1  # max concurrent tasks within this phase

    def __post_init__(self):
        if not self.mode or not isinstance(self.mode, str):
            raise ValueError("Each workflow phase requires a non-empty 'mode'.")
        if not isinstance(self.parallel, int) or self.parallel < 1:
            raise ValueError(f"phase '{self.mode}': 'parallel' must be an int >= 1.")


@dataclass
class ReportSpec:
    formats: list[str] = field(default_factory=lambda: ["html", "md", "json"])
    name: str = ""
    client: str = ""
    logo: str = ""


@dataclass
class Campaign:
    name: str
    targets: list[str]
    workflow: list[Phase]
    workspace: str = ""  # Sn1per workspace alias; defaults to a slug of name
    report: ReportSpec = field(default_factory=ReportSpec)

    def __post_init__(self):
        if not self.targets:
            raise ValueError("A campaign needs at least one target.")
        if not self.workflow:
            raise ValueError("A campaign needs at least one workflow phase.")


@dataclass
class Task:
    """A single unit of execution: one mode against one target."""

    id: str
    phase_index: int
    mode: str
    target: str
    workspace: str
    options: dict[str, Any] = field(default_factory=dict)
    command: list[str] = field(default_factory=list)


@dataclass
class TaskResult:
    task: Task
    status: str = "pending"  # pending | running | done | failed | skipped
    returncode: int | None = None
    started_at: str = ""
    ended_at: str = ""
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["command"] = " ".join(self.task.command)
        return data


@dataclass
class CampaignResult:
    campaign: str
    workspace: str
    started_at: str = ""
    ended_at: str = ""
    dry_run: bool = False
    tasks: list[TaskResult] = field(default_factory=list)
    reports: dict[str, str] = field(default_factory=dict)

    @property
    def failed(self) -> list[TaskResult]:
        return [t for t in self.tasks if t.status == "failed"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign": self.campaign,
            "workspace": self.workspace,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "dry_run": self.dry_run,
            "total_tasks": len(self.tasks),
            "failed_tasks": len(self.failed),
            "tasks": [t.to_dict() for t in self.tasks],
            "reports": self.reports,
        }
