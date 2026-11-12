"""ScopeService: validated, tenant-scoped, audited scope management."""

import uuid
from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome, NetworkClass, Role, ScopeKind
from neo_orchestro.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from neo_orchestro.db.models import AuditLog, ScopeEntry, User
from neo_orchestro.scope import DenyReason, StaticResolver
from neo_orchestro.services.scope import ScopeService
from support import Tenant, principal_of

MakeTenant = Callable[..., Tenant]
MakeUser = Callable[..., User]
RESOLVER = StaticResolver({"app.acme.example.com": ["93.184.216.34"]})


def service_for(session: Session, settings: Settings, user: User) -> ScopeService:
    return ScopeService(session, principal_of(user), settings)


@pytest.mark.integration
def test_admin_adds_normalised_entries(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    svc = service_for(db_session, settings, tenant.admin)

    domain = svc.add_entry(ScopeKind.domain, "App.Acme.Example.com.", include_subdomains=True)
    cidr = svc.add_entry(ScopeKind.cidr, "10.20.0.0/16", description="lab")
    assert (domain.value, domain.include_subdomains, domain.network_class) == (
        "app.acme.example.com",
        True,
        NetworkClass.external,
    )
    assert cidr.network_class is NetworkClass.internal
    assert cidr.description == "lab"
    assert cidr.created_by_id == tenant.admin.id
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "scope.create")).all()


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    ("kind", "value"),
    [
        (ScopeKind.cidr, "0.0.0.0/0"),
        (ScopeKind.cidr, "10.0.0.0/8"),
        (ScopeKind.ip, "127.0.0.1"),
        (ScopeKind.ip, "169.254.169.254"),
        (ScopeKind.domain, "*.example.com"),
        (ScopeKind.domain, "com"),
    ],
)
def test_dangerous_entries_are_refused_and_audited(
    db_session: Session, settings: Settings, make_tenant: MakeTenant, kind: ScopeKind, value: str
) -> None:
    tenant = make_tenant()
    with pytest.raises(ValidationFailedError):
        service_for(db_session, settings, tenant.admin).add_entry(kind, value)
    denied = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "scope.create", AuditLog.outcome == AuditOutcome.denied
        )
    ).all()
    assert len(denied) == 1


@pytest.mark.integration
def test_the_prefix_limit_comes_from_settings(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    loose = settings.model_copy(update={"scope_min_prefix_v4": 8})
    assert service_for(db_session, loose, tenant.admin).add_entry(ScopeKind.cidr, "10.0.0.0/8")


@pytest.mark.integration
def test_duplicate_entries_conflict(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    svc = service_for(db_session, settings, make_tenant().admin)
    svc.add_entry(ScopeKind.domain, "example.com")
    with pytest.raises(ConflictError):
        svc.add_entry(ScopeKind.domain, "EXAMPLE.com.")


@pytest.mark.integration
@pytest.mark.security
def test_only_admins_change_scope_but_everyone_can_read_it(
    db_session: Session, settings: Settings, make_tenant: MakeTenant, make_user: MakeUser
) -> None:
    tenant = make_tenant()
    entry = service_for(db_session, settings, tenant.admin).add_entry(
        ScopeKind.domain, "example.com"
    )
    for role in (Role.analyst, Role.viewer):
        svc = service_for(
            db_session, settings, make_user(tenant, f"{role.value}@acme.example.com", role)
        )
        assert [e.id for e in svc.list_entries()] == [entry.id]
        with pytest.raises(PermissionDeniedError):
            svc.add_entry(ScopeKind.domain, "other.example.com")
        with pytest.raises(PermissionDeniedError):
            svc.delete_entry(entry.id)


@pytest.mark.integration
@pytest.mark.security
def test_other_organisations_entries_are_invisible_and_undeletable(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    foreign = service_for(db_session, settings, globex.admin).add_entry(
        ScopeKind.domain, "globex.example.com"
    )
    svc = service_for(db_session, settings, acme.admin)

    assert svc.list_entries() == []
    with pytest.raises(NotFoundError):
        svc.delete_entry(foreign.id)
    with pytest.raises(NotFoundError):
        svc.delete_entry(uuid.uuid4())
    assert db_session.get(ScopeEntry, foreign.id) is not None


@pytest.mark.integration
def test_delete_removes_the_entry_and_audits(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    svc = service_for(db_session, settings, make_tenant().admin)
    entry = svc.add_entry(ScopeKind.domain, "example.com")
    svc.delete_entry(entry.id)
    assert svc.list_entries() == []
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "scope.delete")).all()


@pytest.mark.integration
@pytest.mark.security
def test_check_uses_only_this_organisations_rules_and_is_audited(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    service_for(db_session, settings, acme.admin).add_entry(
        ScopeKind.domain, "app.acme.example.com"
    )
    ok = service_for(db_session, settings, acme.admin).check("app.acme.example.com", RESOLVER)
    assert ok.allowed
    assert ok.pinned_ips == ("93.184.216.34",)

    # Globex has no rules: the same name is out of scope for them.
    other = service_for(db_session, settings, globex.admin).check("app.acme.example.com", RESOLVER)
    assert other.reason is DenyReason.not_in_scope

    outcomes = {
        e.outcome
        for e in db_session.scalars(select(AuditLog).where(AuditLog.action == "scope.check"))
    }
    assert outcomes == {AuditOutcome.success, AuditOutcome.denied}


@pytest.mark.integration
def test_rules_are_returned_as_engine_ready_objects(
    db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    svc = service_for(db_session, settings, make_tenant().admin)
    entry = svc.add_entry(ScopeKind.cidr, "10.20.0.0/16")
    [rule] = svc.rules()
    assert (rule.id, rule.value, rule.network_class) == (
        str(entry.id),
        "10.20.0.0/16",
        NetworkClass.internal,
    )
