"""Scan execution (worker side): scope re-validation, idempotency, cancellation, failures."""

import uuid
from collections.abc import Callable, Iterator
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import (
    AuditOutcome,
    FindingCategory,
    ScanStatus,
    ScopeKind,
    Severity,
)
from neo_orchestro.db.models import AuditLog, Finding, ScanJob
from neo_orchestro.engines import (
    DnsReconEngine,
    EngineContext,
    EngineError,
    EngineRegistry,
    NormalisedFinding,
)
from neo_orchestro.orchestrator.runner import WorkerDeps, execute_scan
from neo_orchestro.services.scans import ScanService
from neo_orchestro.services.scope import ScopeService
from support import (
    FakeClock,
    FakeDnsClient,
    InMemoryDispatcher,
    MutableResolver,
    SharedSession,
    Tenant,
    principal_of,
)

MakeTenant = Callable[..., Tenant]


def make_finding(i: int, severity: Severity = Severity.info) -> NormalisedFinding:
    return NormalisedFinding(
        category=FindingCategory.info,
        severity=severity,
        title=f"finding {i}",
        asset="app.acme.example.com",
        key=str(i),
    )


class ScriptedEngine:
    """A test engine whose behaviour is a function of the context."""

    name = "scripted"
    description = "test engine"
    target_kinds = frozenset({ScopeKind.domain})

    def __init__(self, script: Callable[[EngineContext], Iterator[NormalisedFinding]]) -> None:
        self.script = script
        self.runs = 0

    def validate_params(self, params: Any) -> dict[str, Any]:
        return dict(params)

    def run(self, ctx: EngineContext) -> Iterator[NormalisedFinding]:
        self.runs += 1
        return self.script(ctx)


@pytest.fixture
def dns_table() -> dict[str, Any]:
    return {"app.acme.example.com": ["93.184.216.34"]}


@pytest.fixture
def fake_dns() -> FakeDnsClient:
    return FakeDnsClient({"A": ["93.184.216.34"], "TXT": ['"v=spf1 -all"']})


@pytest.fixture
def scripted() -> ScriptedEngine:
    return ScriptedEngine(lambda ctx: iter([make_finding(i) for i in range(3)]))


@pytest.fixture
def deps(
    db_session: Session,
    settings: Settings,
    clock: FakeClock,
    dns_table: dict[str, Any],
    fake_dns: FakeDnsClient,
    scripted: ScriptedEngine,
) -> WorkerDeps:
    return WorkerDeps(
        session_factory=lambda: SharedSession(db_session),
        registry=EngineRegistry([DnsReconEngine(fake_dns), scripted]),
        resolver=MutableResolver(dns_table),
        settings=settings,
        clock=clock,
        poll_interval=0.0,
        max_findings=50,
    )


@pytest.fixture
def new_scan(
    db_session: Session, settings: Settings, deps: WorkerDeps, make_tenant: MakeTenant
) -> Callable[..., tuple[Tenant, ScanJob]]:
    def _new(
        engine: str = "dns_recon", params: dict[str, Any] | None = None
    ) -> tuple[Tenant, ScanJob]:
        tenant = make_tenant()
        ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
            ScopeKind.domain, "acme.example.com", include_subdomains=True
        )
        scan = ScanService(
            db_session, principal_of(tenant.admin), settings, deps.registry, InMemoryDispatcher()
        ).create_scan(engine, "app.acme.example.com", params or {}, deps.resolver)
        return tenant, scan

    return _new


def findings_of(session: Session, scan: ScanJob) -> list[Finding]:
    return list(session.scalars(select(Finding).where(Finding.scan_id == scan.id)))


def finish_audit(session: Session) -> AuditLog:
    return session.scalars(select(AuditLog).where(AuditLog.action == "scan.finish")).one()


# ------------------------------------------------------------------ success


@pytest.mark.integration
def test_a_scan_runs_to_completion_and_persists_normalised_findings(
    db_session: Session, deps: WorkerDeps, new_scan: Callable[..., tuple[Tenant, ScanJob]]
) -> None:
    tenant, scan = new_scan()
    assert execute_scan(deps, scan.id) is ScanStatus.succeeded

    db_session.refresh(scan)
    assert scan.status is ScanStatus.succeeded
    assert scan.attempts == 1
    assert scan.started_at is not None
    assert scan.finished_at is not None
    assert scan.error_code is None
    assert scan.scope_decision is not None
    assert scan.scope_decision["pinned_ips"] == ["93.184.216.34"]

    rows = findings_of(db_session, scan)
    assert {f.title for f in rows} == {"A record", "TXT record"}
    assert all(f.org_id == tenant.org.id and f.source_engine == "dns_recon" for f in rows)
    assert all(len(f.fingerprint) == 64 for f in rows)

    entry = finish_audit(db_session)
    assert entry.outcome is AuditOutcome.success
    assert entry.actor_user_id == tenant.admin.id
    assert entry.details["findings"] == 2


@pytest.mark.integration
@pytest.mark.security
def test_engines_receive_the_validated_pinned_addresses_not_a_fresh_resolution(
    deps: WorkerDeps, scripted: ScriptedEngine, new_scan: Callable[..., tuple[Tenant, ScanJob]]
) -> None:
    seen: dict[str, Any] = {}

    def script(ctx: EngineContext) -> Iterator[NormalisedFinding]:
        seen.update(ips=ctx.pinned_ips, target=ctx.target, params=dict(ctx.params))
        yield make_finding(0)

    scripted.script = script
    _, scan = new_scan("scripted", {"depth": 2})
    execute_scan(deps, scan.id)
    assert seen["ips"] == ("93.184.216.34",)  # the addresses scope validated at execution time
    assert seen["target"] == "app.acme.example.com"
    assert seen["params"] == {"depth": 2}


@pytest.mark.integration
def test_duplicate_findings_are_stored_once(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    scripted.script = lambda ctx: iter([make_finding(1), make_finding(1), make_finding(2)])
    _, scan = new_scan("scripted")
    execute_scan(deps, scan.id)
    assert len(findings_of(db_session, scan)) == 2


@pytest.mark.integration
def test_terminal_and_missing_scans_are_not_rerun(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    _, scan = new_scan("scripted")
    assert execute_scan(deps, scan.id) is ScanStatus.succeeded
    assert execute_scan(deps, scan.id) is None  # redelivered message for a finished scan
    assert execute_scan(deps, uuid.uuid4()) is None
    assert scripted.runs == 1
    assert len(findings_of(db_session, scan)) == 3


# ------------------------------------------------------------------ scope re-validation


@pytest.mark.integration
@pytest.mark.security
def test_dns_rebinding_between_request_and_execution_is_caught(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    dns_table: dict[str, Any],
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    _, scan = new_scan("scripted")
    dns_table["app.acme.example.com"] = ["127.0.0.1"]  # the attacker flips the record

    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "scope_denied"
    assert "blocked_address" in (scan.error_message or "")
    assert scan.scope_decision is not None
    assert scan.scope_decision["allowed"] is False
    assert scripted.runs == 0  # the engine never started
    assert findings_of(db_session, scan) == []
    assert finish_audit(db_session).outcome is AuditOutcome.denied


@pytest.mark.integration
@pytest.mark.security
def test_a_scope_rule_removed_after_queuing_stops_the_scan(
    db_session: Session,
    settings: Settings,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    tenant, scan = new_scan("scripted")
    service = ScopeService(db_session, principal_of(tenant.admin), settings)
    for entry in service.list_entries():
        service.delete_entry(entry.id)

    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "scope_denied"
    assert "not_in_scope" in (scan.error_message or "")
    assert scripted.runs == 0


@pytest.mark.integration
@pytest.mark.security
def test_an_engine_removed_from_the_allowlist_fails_the_scan(
    db_session: Session, deps: WorkerDeps, new_scan: Callable[..., tuple[Tenant, ScanJob]]
) -> None:
    _, scan = new_scan()
    scan.engine = "nmap"  # e.g. a row edited out-of-band, or an engine retired since queuing
    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "unknown_engine"


@pytest.mark.integration
def test_invalid_stored_parameters_fail_the_scan(
    db_session: Session, deps: WorkerDeps, new_scan: Callable[..., tuple[Tenant, ScanJob]]
) -> None:
    _, scan = new_scan()
    scan.params = {"record_types": ["AXFR"]}
    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "invalid_params"


# ------------------------------------------------------------------ cancellation


@pytest.mark.integration
def test_a_scan_cancelled_before_it_starts_never_runs(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    _, scan = new_scan("scripted")
    scan.cancel_requested_at = datetime.now(UTC)  # requested while it was still queued
    assert execute_scan(deps, scan.id) is ScanStatus.cancelled
    db_session.refresh(scan)
    assert scan.status is ScanStatus.cancelled
    assert scan.finished_at is not None
    assert scripted.runs == 0


@pytest.mark.integration
def test_a_running_scan_stops_at_its_next_checkpoint_and_keeps_partial_results(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    _, scan = new_scan("scripted")

    def script(ctx: EngineContext) -> Iterator[NormalisedFinding]:
        for i in range(10):
            ctx.check()
            if i == 3:  # the user clicks "cancel" while the scan is running
                scan.cancel_requested_at = datetime.now(UTC)
                db_session.flush()
            yield make_finding(i)

    scripted.script = script
    assert execute_scan(deps, scan.id) is ScanStatus.cancelled
    db_session.refresh(scan)
    assert scan.status is ScanStatus.cancelled
    assert 0 < len(findings_of(db_session, scan)) < 10  # partial results kept
    assert finish_audit(db_session).details["status"] == "cancelled"


# ------------------------------------------------------------------ failures


@pytest.mark.integration
def test_engine_errors_fail_the_scan_with_a_stable_code_and_keep_partial_results(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    def script(ctx: EngineContext) -> Iterator[NormalisedFinding]:
        yield make_finding(1)
        raise EngineError("dns_error", "A lookup failed: Timeout")

    scripted.script = script
    _, scan = new_scan("scripted")
    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert (scan.error_code, scan.error_message) == ("dns_error", "A lookup failed: Timeout")
    assert len(findings_of(db_session, scan)) == 1
    assert finish_audit(db_session).outcome is AuditOutcome.failure


@pytest.mark.integration
@pytest.mark.security
def test_unexpected_errors_never_leak_internals(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    def script(ctx: EngineContext) -> Iterator[NormalisedFinding]:
        raise RuntimeError("password=hunter2 at /srv/neo/secret.py line 12")
        yield make_finding(0)  # pragma: no cover

    scripted.script = script
    _, scan = new_scan("scripted")
    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "internal_error"
    assert "hunter2" not in (scan.error_message or "")
    assert "/srv/neo" not in (scan.error_message or "")


@pytest.mark.integration
def test_the_maximum_duration_is_enforced(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    settings: Settings,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    def script(ctx: EngineContext) -> Iterator[NormalisedFinding]:
        ctx.check()
        yield make_finding(0)

    scripted.script = script
    _, scan = new_scan("scripted")
    no_time = settings.model_copy(update={"scan_max_duration_seconds": 0})
    expired = replace(deps, settings=no_time)
    assert execute_scan(expired, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "timeout"


@pytest.mark.integration
@pytest.mark.security
def test_runaway_engines_are_stopped_by_the_findings_cap(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    scripted.script = lambda ctx: (make_finding(i) for i in range(10_000))
    _, scan = new_scan("scripted")
    assert execute_scan(deps, scan.id) is ScanStatus.failed  # deps.max_findings == 50
    db_session.refresh(scan)
    assert scan.error_code == "too_many_findings"
    assert len(findings_of(db_session, scan)) <= 50


# ------------------------------------------------------------------ redelivery / resume


@pytest.mark.integration
def test_a_scan_interrupted_by_a_worker_crash_resumes_without_duplicates(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    tenant, scan = new_scan("scripted")
    # State a crashed worker leaves behind: running, one attempt, one finding already stored.
    scan.status = ScanStatus.running
    scan.attempts = 1
    scan.started_at = datetime.now(UTC)
    db_session.add(
        Finding(
            org_id=tenant.org.id,
            scan_id=scan.id,
            category=FindingCategory.info,
            severity=Severity.info,
            title="finding 0",
            asset="app.acme.example.com",
            fingerprint=make_finding(0).fingerprint,
            source_engine="scripted",
        )
    )
    db_session.flush()

    assert execute_scan(deps, scan.id) is ScanStatus.succeeded  # broker redelivered the task
    db_session.refresh(scan)
    assert scan.attempts == 2
    assert len(findings_of(db_session, scan)) == 3  # 0 was not duplicated


@pytest.mark.integration
def test_a_scan_that_keeps_crashing_workers_is_given_up_on(
    db_session: Session,
    deps: WorkerDeps,
    scripted: ScriptedEngine,
    new_scan: Callable[..., tuple[Tenant, ScanJob]],
) -> None:
    _, scan = new_scan("scripted")
    scan.status = ScanStatus.running
    scan.attempts = 3  # deps.max_attempts
    assert execute_scan(deps, scan.id) is ScanStatus.failed
    db_session.refresh(scan)
    assert scan.error_code == "max_attempts_exceeded"
    assert scripted.runs == 0
