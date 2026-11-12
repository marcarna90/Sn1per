"""The Celery task: a thin shell around ``execute_scan``."""

import uuid
from collections.abc import Callable
from typing import Any

from celery import Celery

from neo_orchestro.orchestrator.celery_app import TASK_NAME
from neo_orchestro.orchestrator.runner import WorkerDeps, execute_scan


def register_tasks(app: Celery, deps_provider: Callable[[], WorkerDeps]) -> Any:
    """Register ``run_scan`` on ``app``. ``deps_provider`` is called lazily inside the worker
    process (after fork), so database connections are never shared across processes."""

    def run_scan(scan_id: str) -> str | None:
        status = execute_scan(deps_provider(), uuid.UUID(scan_id))
        return status.value if status else None

    # Applied by call (not as a decorator syntax): Celery ships no type stubs.
    return app.task(name=TASK_NAME, acks_late=True)(run_scan)
