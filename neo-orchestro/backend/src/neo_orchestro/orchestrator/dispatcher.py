"""Publishes scan ids to the Celery queue."""

import uuid

from celery import Celery

from neo_orchestro.core.config import Settings
from neo_orchestro.orchestrator.celery_app import QUEUE, TASK_NAME, create_celery
from neo_orchestro.services.scans import DispatchError


class CeleryDispatcher:
    """Implements ``services.scans.ScanDispatcher``. Sends by task *name*, so the API never
    imports worker code."""

    def __init__(self, settings: Settings, app: Celery | None = None) -> None:
        self._app = app or create_celery(settings)

    def enqueue(self, scan_id: uuid.UUID) -> str:
        try:
            result = self._app.send_task(TASK_NAME, args=[str(scan_id)], queue=QUEUE)
        except Exception as exc:  # kombu/redis raise many types; never leak broker URLs
            raise DispatchError(f"could not publish the task ({type(exc).__name__})") from exc
        return str(result.id)
