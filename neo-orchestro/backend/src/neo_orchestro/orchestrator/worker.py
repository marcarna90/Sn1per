"""Worker entry point::

    celery -A neo_orchestro.orchestrator.worker:app worker -Q scans --concurrency 2

Configuration comes from ``NEO_*`` environment variables (same as the API).
"""

from functools import lru_cache

from neo_orchestro.core.config import get_settings
from neo_orchestro.core.logging import configure_logging
from neo_orchestro.db.session import get_session_factory
from neo_orchestro.engines import default_registry
from neo_orchestro.orchestrator.celery_app import create_celery
from neo_orchestro.orchestrator.runner import WorkerDeps
from neo_orchestro.orchestrator.tasks import register_tasks
from neo_orchestro.scope import DnsPythonResolver

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json)
app = create_celery(settings)


@lru_cache
def _deps() -> WorkerDeps:
    return WorkerDeps(
        session_factory=get_session_factory(),
        registry=default_registry(settings),
        resolver=DnsPythonResolver(
            timeout=settings.dns_timeout_seconds, nameservers=settings.dns_nameservers
        ),
        settings=settings,
    )


run_scan = register_tasks(app, _deps)
