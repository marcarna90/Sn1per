"""Hardened Celery application factory.

* JSON only: a poisoned broker message can never reach ``pickle``.
* ``acks_late`` + ``reject_on_worker_lost``: at-least-once delivery that survives a worker
  crash (the runner is idempotent, see ``runner.execute_scan``).
* One message prefetched per worker process, so long scans do not hoard the queue.
* No result backend: outcomes live in PostgreSQL, not in the broker.
"""

from celery import Celery

from neo_orchestro.core.config import Settings

TASK_NAME = "neo_orchestro.run_scan"
QUEUE = "scans"


def create_celery(settings: Settings) -> Celery:
    app = Celery("neo_orchestro", broker=settings.redis_url.get_secret_value())
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        task_ignore_result=True,
        task_default_queue=QUEUE,
        # Hard limits sit above the engine's own deadline so a clean "timeout" wins.
        task_time_limit=settings.scan_max_duration_seconds + 60,
        task_soft_time_limit=settings.scan_max_duration_seconds + 30,
        worker_hijack_root_logger=False,  # keep structlog's configuration
        broker_connection_retry_on_startup=True,
        broker_transport_options={
            # An unacknowledged scan is redelivered only after it must have died.
            "visibility_timeout": settings.scan_max_duration_seconds + 300,
            "socket_connect_timeout": 3,
            "socket_timeout": 5,
        },
        task_publish_retry_policy={
            "max_retries": 1,
            "interval_start": 0,
            "interval_step": 0.2,
            "interval_max": 0.2,
        },
    )
    return app
