"""Pluggable execution backends for orchestrated tasks.

The runner never shells out directly; it talks to an :class:`Executor`. This
keeps the scheduling logic testable (via :class:`DryRunExecutor`) and isolates
the only side-effecting code path (:class:`SniperExecutor`) behind one class.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone

from jarvis.orchestrate.model import Task, TaskResult


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Executor:
    """Base executor interface."""

    dry_run = False

    def execute(self, task: Task) -> TaskResult:  # pragma: no cover - interface
        raise NotImplementedError


class DryRunExecutor(Executor):
    """Record what would run, without touching the system. Always succeeds."""

    dry_run = True

    def execute(self, task: Task) -> TaskResult:
        ts = _now()
        return TaskResult(
            task=task,
            status="done",
            returncode=0,
            started_at=ts,
            ended_at=ts,
            note="dry-run (not executed)",
        )


class SniperExecutor(Executor):
    """Run the real ``sniper`` command as a subprocess.

    Requires Sn1per (and typically root) on the host. Not exercised in the
    test suite; selected only when the user drops ``--dry-run``.
    """

    def __init__(self, cwd: str | None = None, timeout: int | None = None):
        self.cwd = cwd
        self.timeout = timeout

    def execute(self, task: Task) -> TaskResult:
        result = TaskResult(task=task, status="running", started_at=_now())
        try:
            proc = subprocess.run(
                task.command,
                cwd=self.cwd,
                timeout=self.timeout,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.STDOUT,
            )
            result.returncode = proc.returncode
            result.status = "done" if proc.returncode == 0 else "failed"
            if proc.returncode != 0:
                result.note = f"sniper exited with code {proc.returncode}"
        except FileNotFoundError:
            result.status = "failed"
            result.note = "sniper binary not found in PATH"
        except subprocess.TimeoutExpired:
            result.status = "failed"
            result.note = f"timed out after {self.timeout}s"
        except OSError as exc:
            result.status = "failed"
            result.note = f"execution error: {exc}"
        result.ended_at = _now()
        return result
