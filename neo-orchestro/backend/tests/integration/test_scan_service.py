"""ScanService: create (scope pre-check, allowlist), list, get, findings, cancel."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import (
    AuditOutcome,
    FindingCategory,
    Role,
    ScanStatus,
    ScopeKind,
    Severity,
)
from neo_orchestro.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ScopeViolationError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from neo_orchestro.db.models import AuditLog, Finding, ScanJob, User
from neo_orchestro.engines import DnsReconEngine, EngineRegistry
from neo_orchestro.scope import StaticResolver
from neo_orchestro.services.scans import DispatchError, ScanService
from neo_orchestro.services.scope import ScopeService
from support import FakeDnsClient, InMemoryDispatcher, Tenant, principal_of

MakeTenant = Callable[..., Tenant]
MakeUser = Callable[..., User]
DNS = {
    "app.acme.example.com": ["93.184.216.34"],
    "evil.acme.example.com": ["127.0.0.1"],
}


@pytest.fixture
def registry() -> EngineRegistry:
    return EngineRegistry([DnsReconEngine(FakeDnsClient())])


@pytest.fixture
def dispatcher() -> InMemoryDispatcher:
    return InMemoryDispatcher()


@pytest.fixture
def make_service(
    db_session: Session,
    settings: Settings,
    registry: EngineRegistry,
    dispatcher: InMemoryDispatcher,
) -> Callable[..., ScanService]:
    def _make(user: User, **kw: Any) -> ScanService:
        return ScanService(
            db_session,
            principal_of(user),
            settings,
            kw.get("registry", registry),
            kw.get("dispatcher", dispatcher),
        )

    return _make


@pytest.fixture
def authorise(db_session: Session, settings: Settings) -> Callable[[Tenant, str], None]:
    def _authorise(tenant: Tenant, domain: str = "acme.example.com") -> None:
        ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
            ScopeKind.domain, domain, include_subdomains=True
        )

    return _authorise


def audit(session: Session, action: str) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


RESOLVER = StaticResolver(DNS)


# ------------------------------------------------------------------ create


@pytest.mark.integration
def test_create_records_who_what_when_and_dispatches_once(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
    dispatcher: InMemoryDispatcher,
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    scan = make_service(tenant.admin).create_scan(
        "dns_recon", "APP.Acme.Example.com.", {"record_types": ["a", "mx"]}, RESOLVER
    )

    assert scan.status is ScanStatus.pending
    assert scan.engine == "dns_recon"
    assert scan.target == "app.acme.example.com"  # normalised
    assert scan.params == {"record_types": ["A", "MX"]}  # validated + normalised
    assert scan.requested_by_id == tenant.admin.id
    assert scan.org_id == tenant.org.id
    assert scan.scope_decision is not None
    assert scan.scope_decision["allowed"] is True
    assert scan.scope_decision["pinned_ips"] == ["93.184.216.34"]
    assert scan.created_at is not None
    assert dispatcher.ids == [scan.id]
    assert scan.celery_task_id == "task-1"
    [entry] = audit(db_session, "scan.create")
    assert entry.outcome is AuditOutcome.success
    assert entry.resource_id == str(scan.id)


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    "engine_name",
    ["nmap", "dns_recon; rm -rf /", "../dns_recon", "DNS_RECON", "", "$(id)", "a" * 500],
)
def test_only_allowlisted_engines_can_be_requested(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
    dispatcher: InMemoryDispatcher,
    engine_name: str,
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    with pytest.raises(ValidationFailedError, match="unknown engine"):
        make_service(tenant.admin).create_scan(engine_name, "app.acme.example.com", {}, RESOLVER)
    assert dispatcher.ids == []
    assert db_session.scalars(select(ScanJob)).all() == []
    [entry] = audit(db_session, "scan.create")
    assert entry.outcome is AuditOutcome.denied
    assert len(str(entry.details)) < 400  # a hostile name is truncated, not stored whole


@pytest.mark.integration
@pytest.mark.parametrize(
    "params", [{"record_types": ["AXFR"]}, {"nameserver": "8.8.8.8"}, {"record_types": "A"}]
)
def test_invalid_engine_params_are_rejected(
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
    params: dict[str, Any],
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    with pytest.raises(ValidationFailedError):
        make_service(tenant.admin).create_scan(
            "dns_recon", "app.acme.example.com", params, RESOLVER
        )


@pytest.mark.integration
def test_the_target_kind_must_suit_the_engine(
    make_tenant: MakeTenant,
    make_service: Callable[..., ScanService],
    db_session: Session,
    settings: Settings,
) -> None:
    tenant = make_tenant()
    ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
        ScopeKind.ip, "93.184.216.34"
    )
    with pytest.raises(ValidationFailedError, match="domain"):  # dns_recon is domain-only
        make_service(tenant.admin).create_scan("dns_recon", "93.184.216.34", {}, RESOLVER)


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    ("target", "reason"),
    [
        ("notauthorised.example.org", "not_in_scope"),
        ("evil.acme.example.com", "blocked_address"),  # authorised name resolving to loopback
        ("http://app.acme.example.com", "invalid_target"),
    ],
)
def test_out_of_scope_targets_are_refused_before_anything_is_queued(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
    dispatcher: InMemoryDispatcher,
    target: str,
    reason: str,
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    with pytest.raises(ScopeViolationError) as caught:
        make_service(tenant.admin).create_scan("dns_recon", target, {}, RESOLVER)
    assert caught.value.details["reason"] == reason
    assert dispatcher.ids == []
    assert db_session.scalars(select(ScanJob)).all() == []
    [entry] = audit(db_session, "scan.create")
    assert entry.outcome is AuditOutcome.denied
    assert entry.details["reason"] == reason


@pytest.mark.integration
@pytest.mark.security
def test_roles(
    make_tenant: MakeTenant,
    make_user: MakeUser,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    viewer = make_user(tenant, "viewer@acme.example.com", Role.viewer)
    analyst = make_user(tenant, "analyst@acme.example.com", Role.analyst)

    with pytest.raises(PermissionDeniedError):
        make_service(viewer).create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER)
    scan = make_service(analyst).create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER)

    assert [s.id for s in make_service(viewer).list_scans()] == [scan.id]  # read-only access
    assert make_service(viewer).get_scan(scan.id).id == scan.id
    with pytest.raises(PermissionDeniedError):
        make_service(viewer).cancel_scan(scan.id)


@pytest.mark.integration
def test_a_broken_queue_fails_the_scan_cleanly(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    class Broken:
        def enqueue(self, scan_id: uuid.UUID) -> str:
            raise DispatchError("redis://:secret@10.0.0.5 unreachable")

    tenant = make_tenant()
    authorise(tenant)
    with pytest.raises(ServiceUnavailableError) as caught:
        make_service(tenant.admin, dispatcher=Broken()).create_scan(
            "dns_recon", "app.acme.example.com", {}, RESOLVER
        )
    assert "secret" not in str(caught.value)
    [scan] = db_session.scalars(select(ScanJob)).all()
    assert scan.status is ScanStatus.failed
    assert scan.error_code == "dispatch_failed"
    assert scan.finished_at is not None


# ------------------------------------------------------------------ read


@pytest.mark.integration
def test_listing_is_newest_first_filterable_and_paginated(
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    service = make_service(tenant.admin)
    created = [
        service.create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER) for _ in range(3)
    ]
    created[0].status = ScanStatus.succeeded

    assert [s.id for s in service.list_scans()] == [c.id for c in reversed(created)]
    assert [s.id for s in service.list_scans(status=ScanStatus.succeeded)] == [created[0].id]
    page = service.list_scans(limit=1, offset=1)
    assert [s.id for s in page] == [created[1].id]


@pytest.mark.integration
@pytest.mark.security
def test_scans_and_findings_of_other_organisations_are_invisible(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    authorise(acme)
    authorise(globex, "globex.example.com")
    globex_dns = StaticResolver({"www.globex.example.com": ["93.184.216.34"]})
    theirs = make_service(globex.admin).create_scan(
        "dns_recon", "www.globex.example.com", {}, globex_dns
    )
    db_session.add(
        Finding(
            org_id=globex.org.id,
            scan_id=theirs.id,
            category=FindingCategory.info,
            severity=Severity.low,
            title="secret finding",
            asset="www.globex.example.com",
            fingerprint="a" * 64,
            source_engine="dns_recon",
        )
    )
    db_session.flush()

    mine = make_service(acme.admin)
    assert mine.list_scans() == []
    with pytest.raises(NotFoundError):
        mine.get_scan(theirs.id)
    with pytest.raises(NotFoundError):
        mine.list_findings(theirs.id)
    with pytest.raises(NotFoundError):
        mine.cancel_scan(theirs.id)
    db_session.refresh(theirs)
    assert theirs.status is ScanStatus.pending


@pytest.mark.integration
def test_findings_can_be_filtered_by_severity(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    service = make_service(tenant.admin)
    scan = service.create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER)
    for i, severity in enumerate([Severity.info, Severity.low, Severity.low]):
        db_session.add(
            Finding(
                org_id=tenant.org.id,
                scan_id=scan.id,
                category=FindingCategory.info,
                severity=severity,
                title=f"t{i}",
                asset="app.acme.example.com",
                fingerprint=f"{i}" * 64,
                source_engine="dns_recon",
            )
        )
    db_session.flush()
    assert len(service.list_findings(scan.id)) == 3
    assert [f.severity for f in service.list_findings(scan.id, severity=Severity.low)] == [
        Severity.low,
        Severity.low,
    ]
    assert len(service.list_findings(scan.id, limit=1, offset=1)) == 1


# ------------------------------------------------------------------ cancel


@pytest.mark.integration
def test_cancelling_a_pending_scan_takes_effect_immediately(
    db_session: Session,
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    service = make_service(tenant.admin)
    scan = service.create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER)

    cancelled = service.cancel_scan(scan.id)
    assert cancelled.status is ScanStatus.cancelled
    assert cancelled.cancel_requested_at is not None
    assert cancelled.finished_at is not None
    assert audit(db_session, "scan.cancel")


@pytest.mark.integration
def test_cancelling_a_running_scan_is_cooperative(
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    service = make_service(tenant.admin)
    scan = service.create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER)
    scan.status = ScanStatus.running
    scan.started_at = datetime.now(UTC)

    result = service.cancel_scan(scan.id)
    assert result.status is ScanStatus.running  # the worker stops it at its next checkpoint
    assert result.cancel_requested_at is not None
    assert result.finished_at is None


@pytest.mark.integration
@pytest.mark.parametrize("final", [ScanStatus.succeeded, ScanStatus.failed, ScanStatus.cancelled])
def test_finished_scans_cannot_be_cancelled(
    make_tenant: MakeTenant,
    authorise: Callable[..., None],
    make_service: Callable[..., ScanService],
    final: ScanStatus,
) -> None:
    tenant = make_tenant()
    authorise(tenant)
    service = make_service(tenant.admin)
    scan = service.create_scan("dns_recon", "app.acme.example.com", {}, RESOLVER)
    scan.status = final
    with pytest.raises(ConflictError):
        service.cancel_scan(scan.id)


@pytest.mark.integration
def test_the_engine_catalogue_is_exposed(
    make_tenant: MakeTenant, make_service: Callable[..., ScanService]
) -> None:
    tenant = make_tenant()
    [engine] = make_service(tenant.admin).engines()
    assert engine.name == "dns_recon"
