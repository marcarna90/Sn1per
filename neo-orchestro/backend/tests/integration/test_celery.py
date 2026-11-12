"""Celery wiring: hardened configuration, task execution, real broker publishing."""

import base64
import json
import time
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
import redis
from pydantic import SecretStr
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import ScanStatus, ScopeKind
from neo_orchestro.engines import DnsReconEngine, EngineRegistry
from neo_orchestro.orchestrator.celery_app import TASK_NAME, create_celery
from neo_orchestro.orchestrator.dispatcher import CeleryDispatcher
from neo_orchestro.orchestrator.runner import WorkerDeps
from neo_orchestro.orchestrator.tasks import register_tasks
from neo_orchestro.scope import StaticResolver
from neo_orchestro.services.scans import DispatchError, ScanService
from neo_orchestro.services.scope import ScopeService
from support import (
    FakeClock,
    FakeDnsClient,
    InMemoryDispatcher,
    SharedSession,
    Tenant,
    principal_of,
)


@pytest.mark.integration
@pytest.mark.security
def test_celery_is_configured_for_safety_and_reliability(settings: Settings) -> None:
    conf = create_celery(settings).conf
    # JSON only: a poisoned broker message must never reach pickle.
    assert conf.task_serializer == "json"
    assert list(conf.accept_content) == ["json"]
    assert conf.result_serializer == "json"
    # At-least-once delivery that survives worker crashes; one message per worker at a time.
    assert conf.task_acks_late is True
    assert conf.task_reject_on_worker_lost is True
    assert conf.worker_prefetch_multiplier == 1
    # Results live in PostgreSQL, not in the broker.
    assert conf.task_ignore_result is True
    assert conf.task_default_queue == "scans"
    assert conf.task_time_limit == settings.scan_max_duration_seconds + 60
    assert conf.task_soft_time_limit == settings.scan_max_duration_seconds + 30
    assert conf.worker_hijack_root_logger is False  # keep our structured logging
    assert conf.broker_connection_retry_on_startup is True


@pytest.fixture
def deps(db_session: Session, settings: Settings, clock: FakeClock) -> WorkerDeps:
    return WorkerDeps(
        session_factory=lambda: SharedSession(db_session),
        registry=EngineRegistry([DnsReconEngine(FakeDnsClient({"A": ["93.184.216.34"]}))]),
        resolver=StaticResolver({"app.acme.example.com": ["93.184.216.34"]}),
        settings=settings,
        clock=clock,
        poll_interval=0.0,
    )


@pytest.mark.integration
def test_the_task_runs_a_scan_through_celery(
    db_session: Session,
    settings: Settings,
    deps: WorkerDeps,
    make_tenant: Callable[..., Tenant],
) -> None:
    tenant = make_tenant()
    ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
        ScopeKind.domain, "acme.example.com", include_subdomains=True
    )
    scan = ScanService(
        db_session, principal_of(tenant.admin), settings, deps.registry, InMemoryDispatcher()
    ).create_scan("dns_recon", "app.acme.example.com", {"record_types": ["A"]}, deps.resolver)

    app = create_celery(settings)
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True
    task = register_tasks(app, lambda: deps)

    assert task.name == TASK_NAME == "neo_orchestro.run_scan"
    assert task.apply(args=[str(scan.id)]).get() == "succeeded"
    db_session.refresh(scan)
    assert scan.status is ScanStatus.succeeded

    assert (
        task.apply(args=[str(scan.id)]).get() is None
    )  # a redelivery of a finished scan is a no-op
    assert task.apply(args=[str(uuid.uuid4())]).get() is None


# ------------------------------------------------------------------ broker


@pytest.fixture
def broker(settings: Settings) -> Iterator[redis.Redis]:
    client: redis.Redis = redis.Redis.from_url(settings.redis_url.get_secret_value())
    try:
        client.ping()
    except redis.RedisError:
        pytest.skip("Redis not reachable")  # CI sets NEO_REQUIRE_SERVICES via the conftest engine
    client.delete("scans")
    yield client
    client.delete("scans")
    client.close()


@pytest.mark.integration
@pytest.mark.security
def test_the_dispatcher_publishes_a_json_message_to_the_real_broker(
    settings: Settings, broker: redis.Redis
) -> None:
    scan_id = uuid.uuid4()
    task_id = CeleryDispatcher(settings).enqueue(scan_id)

    assert broker.llen("scans") == 1
    message: dict[str, Any] = json.loads(broker.lindex("scans", 0))  # type: ignore[arg-type]
    assert message["headers"]["task"] == TASK_NAME
    assert message["headers"]["id"] == task_id
    assert message["properties"]["body_encoding"] == "base64"
    args, kwargs, _embed = json.loads(base64.b64decode(message["body"]))
    assert args == [str(scan_id)]  # only an id travels through the broker, never target/params
    assert kwargs == {}
    assert message["content-type"] == "application/json"


@pytest.mark.integration
def test_the_dispatcher_fails_fast_and_without_leaking_credentials(settings: Settings) -> None:
    unreachable = settings.model_copy(
        update={"redis_url": SecretStr("redis://:topsecret@127.0.0.1:1/0")}
    )
    started = time.monotonic()
    with pytest.raises(DispatchError) as caught:
        CeleryDispatcher(unreachable).enqueue(uuid.uuid4())
    assert time.monotonic() - started < 10
    assert "topsecret" not in str(caught.value)
