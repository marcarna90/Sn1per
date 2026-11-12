"""UserService: admin-only user management, tenant isolation, last-admin protection."""

from collections.abc import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome, Role
from neo_orchestro.core.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailedError,
)
from neo_orchestro.db.models import AuditLog, RefreshToken, User
from neo_orchestro.services.auth import AuthService
from neo_orchestro.services.users import UserService
from support import PASSWORD, Tenant, principal_of

MakeTenant = Callable[..., Tenant]
MakeUser = Callable[..., User]


def service_for(session: Session, user: User) -> UserService:
    return UserService(session, principal_of(user))


@pytest.mark.integration
def test_admin_creates_users_in_their_own_organisation(
    db_session: Session, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    created = service_for(db_session, tenant.admin).create_user(
        email="Analyst@Acme.Example.com", password=PASSWORD, role=Role.analyst
    )
    assert created.org_id == tenant.org.id
    assert created.email == "analyst@acme.example.com"
    assert created.role is Role.analyst
    audit = db_session.scalars(select(AuditLog).where(AuditLog.action == "user.create")).one()
    assert audit.actor_user_id == tenant.admin.id
    assert audit.resource_id == str(created.id)
    assert PASSWORD not in str(audit.details)


@pytest.mark.integration
def test_duplicate_emails_and_weak_passwords_are_rejected(
    db_session: Session, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    svc = service_for(db_session, tenant.admin)
    svc.create_user(email="x@acme.example.com", password=PASSWORD, role=Role.viewer)
    with pytest.raises(ConflictError):
        svc.create_user(email="X@acme.example.com", password=PASSWORD, role=Role.viewer)
    with pytest.raises(ValidationFailedError):
        svc.create_user(email="y@acme.example.com", password="short", role=Role.viewer)


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize("role", [Role.analyst, Role.viewer])
def test_only_admins_manage_users(
    db_session: Session, make_tenant: MakeTenant, make_user: MakeUser, role: Role
) -> None:
    tenant = make_tenant()
    actor = make_user(tenant, "actor@acme.example.com", role)
    svc = service_for(db_session, actor)
    with pytest.raises(PermissionDeniedError):
        svc.create_user(email="n@acme.example.com", password=PASSWORD, role=Role.viewer)
    with pytest.raises(PermissionDeniedError):
        svc.list_users()
    with pytest.raises(PermissionDeniedError):
        svc.update_user(tenant.admin.id, role=Role.viewer)


@pytest.mark.integration
@pytest.mark.security
def test_users_of_other_organisations_are_invisible(
    db_session: Session, make_tenant: MakeTenant, make_user: MakeUser
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    foreign = make_user(globex, "victim@globex.example.com")
    svc = service_for(db_session, acme.admin)

    assert {u.id for u in svc.list_users()} == {acme.admin.id}
    with pytest.raises(NotFoundError):
        svc.get_user(foreign.id)
    with pytest.raises(NotFoundError):
        svc.update_user(foreign.id, role=Role.admin)
    db_session.refresh(foreign)
    assert foreign.role is Role.analyst  # untouched


@pytest.mark.integration
def test_admin_can_change_roles(
    db_session: Session, make_tenant: MakeTenant, make_user: MakeUser
) -> None:
    tenant = make_tenant()
    user = make_user(tenant, "u@acme.example.com", Role.viewer)
    updated = service_for(db_session, tenant.admin).update_user(user.id, role=Role.analyst)
    assert updated.role is Role.analyst


@pytest.mark.integration
@pytest.mark.security
def test_the_last_active_admin_cannot_be_demoted_or_deactivated(
    db_session: Session, make_tenant: MakeTenant, make_user: MakeUser
) -> None:
    tenant = make_tenant()
    svc = service_for(db_session, tenant.admin)
    with pytest.raises(ConflictError):
        svc.update_user(tenant.admin.id, role=Role.viewer)
    with pytest.raises(ConflictError):
        svc.update_user(tenant.admin.id, is_active=False)

    second = make_user(tenant, "second@acme.example.com", Role.admin)
    svc.update_user(second.id, is_active=False)  # fine: another active admin remains
    assert second.is_active is False


@pytest.mark.integration
@pytest.mark.security
def test_deactivating_a_user_revokes_their_sessions(
    db_session: Session,
    settings: Settings,
    make_tenant: MakeTenant,
    make_user: MakeUser,
) -> None:
    tenant = make_tenant()
    user = make_user(tenant, "u@acme.example.com")
    pair = AuthService(db_session, settings).login(user.email, PASSWORD)

    service_for(db_session, tenant.admin).update_user(user.id, is_active=False)

    live = db_session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    ).all()
    assert live == []
    assert pair.refresh_token  # the token still decodes, but its family is dead server-side
    audit = db_session.scalars(
        select(AuditLog).where(
            AuditLog.action == "user.update", AuditLog.outcome == AuditOutcome.success
        )
    ).one()
    assert audit.details["is_active"] is False
