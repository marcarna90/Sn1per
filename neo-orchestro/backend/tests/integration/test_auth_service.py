"""AuthService: login, lockout, refresh rotation with reuse detection, logout (ADR 0005)."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome, Role
from neo_orchestro.core.errors import (
    AuthenticationError,
    ConflictError,
    ValidationFailedError,
)
from neo_orchestro.core.security import TokenType, decode_token, issue_access_token
from neo_orchestro.db.models import AuditLog, RefreshToken
from neo_orchestro.services.auth import AuthService
from neo_orchestro.services.context import RequestContext
from neo_orchestro.services.orgs import bootstrap_organization
from support import PASSWORD, FakeClock, Tenant, principal_of

SECRET = "k" * 64
CTX = RequestContext(ip="203.0.113.7", request_id="req-test-0001")
MakeTenant = Callable[..., Tenant]


def audit_rows(session: Session, action: str) -> list[AuditLog]:
    return list(session.scalars(select(AuditLog).where(AuditLog.action == action)))


@pytest.fixture
def auth(db_session: Session, settings: Settings, clock: FakeClock) -> AuthService:
    return AuthService(db_session, settings, clock=clock)


# ------------------------------------------------------------------ bootstrap


@pytest.mark.integration
def test_bootstrap_creates_an_organisation_and_an_admin(
    db_session: Session, settings: Settings
) -> None:
    org, admin = bootstrap_organization(
        db_session,
        name="Acme",
        slug="acme",
        admin_email="Root@Acme.Example.com",
        admin_password=PASSWORD,
    )
    assert admin.org_id == org.id
    assert admin.role is Role.admin
    assert admin.email == "root@acme.example.com"  # normalised
    assert admin.password_hash.startswith("$argon2id$")
    assert PASSWORD not in admin.password_hash
    assert len(audit_rows(db_session, "org.bootstrap")) == 1


@pytest.mark.integration
def test_bootstrap_rejects_weak_passwords_and_duplicates(
    db_session: Session, settings: Settings
) -> None:
    def bootstrap(**overrides: str) -> None:
        args = {
            "name": "Acme",
            "slug": "acme",
            "admin_email": "a@acme.example.com",
            "admin_password": PASSWORD,
        } | overrides
        bootstrap_organization(db_session, **args)

    with pytest.raises(ValidationFailedError):
        bootstrap(admin_password="short")
    bootstrap()
    with pytest.raises(ConflictError):  # same slug
        bootstrap(admin_email="b@acme.example.com")
    with pytest.raises(ConflictError):  # same e-mail, other slug
        bootstrap(slug="other")


# ------------------------------------------------------------------ login


@pytest.mark.integration
def test_login_issues_tokens_and_records_the_session(
    auth: AuthService, db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD, CTX)

    claims = decode_token(
        pair.access_token, secret=SECRET, issuer=settings.jwt_issuer, token_type=TokenType.access
    )
    assert claims.subject == tenant.admin.id
    assert claims.org_id == tenant.admin.org_id
    assert claims.role is Role.admin
    assert pair.access_expires_in == settings.access_token_ttl_minutes * 60

    refresh = decode_token(
        pair.refresh_token, secret=SECRET, issuer=settings.jwt_issuer, token_type=TokenType.refresh
    )
    row = db_session.get(RefreshToken, refresh.jti)
    assert row is not None
    assert row.revoked_at is None
    assert row.family_id == refresh.family_id
    assert tenant.admin.last_login_at is not None

    [entry] = audit_rows(db_session, "auth.login")
    assert entry.outcome is AuditOutcome.success
    assert entry.ip == "203.0.113.7"
    assert entry.request_id == "req-test-0001"
    assert entry.org_id == tenant.admin.org_id


@pytest.mark.integration
def test_login_email_is_case_insensitive(auth: AuthService, make_tenant: MakeTenant) -> None:
    make_tenant()
    assert auth.login("  ADMIN@Acme.Example.COM ", PASSWORD).access_token


@pytest.mark.integration
@pytest.mark.security
def test_wrong_password_and_unknown_user_are_indistinguishable(
    auth: AuthService, db_session: Session, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    errors = []
    for email, password in [
        (tenant.admin.email, "definitely wrong password"),
        ("nobody@nowhere.example.com", PASSWORD),
    ]:
        with pytest.raises(AuthenticationError) as caught:
            auth.login(email, password, CTX)
        errors.append((caught.value.status_code, caught.value.code, str(caught.value)))
    assert errors[0] == errors[1]

    outcomes = [e.outcome for e in audit_rows(db_session, "auth.login")]
    assert outcomes == [AuditOutcome.denied, AuditOutcome.denied]  # both audited


@pytest.mark.integration
@pytest.mark.security
def test_repeated_failures_lock_the_account_until_the_lockout_expires(
    auth: AuthService, clock: FakeClock, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    for _ in range(3):  # login_max_failed_attempts == 3 in the test settings
        with pytest.raises(AuthenticationError):
            auth.login(tenant.admin.email, "wrong password here", CTX)
    assert tenant.admin.locked_until is not None

    with pytest.raises(AuthenticationError):  # even the right password is refused while locked
        auth.login(tenant.admin.email, PASSWORD, CTX)

    clock.advance(minutes=16)
    assert auth.login(tenant.admin.email, PASSWORD, CTX).access_token
    assert tenant.admin.failed_login_attempts == 0
    assert tenant.admin.locked_until is None


@pytest.mark.integration
def test_inactive_users_cannot_log_in(auth: AuthService, make_tenant: MakeTenant) -> None:
    tenant = make_tenant()
    tenant.admin.is_active = False
    with pytest.raises(AuthenticationError):
        auth.login(tenant.admin.email, PASSWORD)


# ------------------------------------------------------------------ refresh rotation


@pytest.mark.integration
@pytest.mark.security
def test_refresh_rotates_the_token_and_keeps_the_family(
    auth: AuthService, db_session: Session, settings: Settings, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    first = auth.login(tenant.admin.email, PASSWORD)
    second = auth.refresh(first.refresh_token, CTX)

    assert second.refresh_token != first.refresh_token
    kw = {"secret": SECRET, "issuer": settings.jwt_issuer, "token_type": "refresh"}
    old = decode_token(first.refresh_token, **kw)  # type: ignore[arg-type]
    new = decode_token(second.refresh_token, **kw)  # type: ignore[arg-type]
    assert old.family_id == new.family_id
    old_row, new_row = db_session.get(RefreshToken, old.jti), db_session.get(RefreshToken, new.jti)
    assert old_row is not None
    assert old_row.revoked_at is not None
    assert new_row is not None
    assert new_row.revoked_at is None


@pytest.mark.integration
@pytest.mark.security
def test_reusing_a_rotated_refresh_token_revokes_the_whole_family(
    auth: AuthService, db_session: Session, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    stolen = auth.login(tenant.admin.email, PASSWORD)
    legitimate = auth.refresh(stolen.refresh_token)

    with pytest.raises(AuthenticationError):  # the thief replays the old token
        auth.refresh(stolen.refresh_token, CTX)
    with pytest.raises(AuthenticationError):  # ...and the legitimate session dies too
        auth.refresh(legitimate.refresh_token)

    [entry] = audit_rows(db_session, "auth.refresh_reuse_detected")
    assert entry.outcome is AuditOutcome.denied
    assert entry.org_id == tenant.admin.org_id


@pytest.mark.integration
def test_refresh_fails_after_the_server_side_expiry(
    auth: AuthService, clock: FakeClock, settings: Settings, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD)
    clock.advance(days=settings.refresh_token_ttl_days, minutes=1)
    with pytest.raises(AuthenticationError):
        auth.refresh(pair.refresh_token)


@pytest.mark.integration
@pytest.mark.security
def test_refresh_fails_for_a_deactivated_user_and_kills_the_family(
    auth: AuthService, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD)
    tenant.admin.is_active = False
    with pytest.raises(AuthenticationError):
        auth.refresh(pair.refresh_token)
    tenant.admin.is_active = True
    with pytest.raises(AuthenticationError):  # reactivation does not resurrect a revoked family
        auth.refresh(pair.refresh_token)


@pytest.mark.integration
@pytest.mark.security
def test_refresh_rejects_access_tokens_and_garbage(
    auth: AuthService, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD)
    for bad in (pair.access_token, "garbage", ""):
        with pytest.raises(AuthenticationError):
            auth.refresh(bad)


@pytest.mark.integration
def test_logout_revokes_the_family_and_is_idempotent(
    auth: AuthService, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD)
    auth.logout(pair.refresh_token, CTX)
    with pytest.raises(AuthenticationError):
        auth.refresh(pair.refresh_token)
    auth.logout(pair.refresh_token)  # again: no error
    auth.logout("garbage")  # garbage: no error


@pytest.mark.integration
@pytest.mark.security
def test_a_stale_token_after_logout_is_refused_without_a_theft_alert(
    auth: AuthService, db_session: Session, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD)
    auth.logout(pair.refresh_token)
    with pytest.raises(AuthenticationError):  # e.g. a forgotten browser tab
        auth.refresh(pair.refresh_token)
    assert audit_rows(db_session, "auth.refresh_reuse_detected") == []
    [entry] = audit_rows(db_session, "auth.refresh")
    assert entry.outcome is AuditOutcome.denied
    assert entry.details == {"reason": "revoked_token"}


# ------------------------------------------------------------------ authenticate


@pytest.mark.integration
@pytest.mark.security
def test_authenticate_returns_the_current_database_role(
    auth: AuthService, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    pair = auth.login(tenant.admin.email, PASSWORD)
    assert auth.authenticate(pair.access_token).role is Role.admin
    tenant.admin.role = Role.viewer  # demoted after the token was issued
    assert auth.authenticate(pair.access_token).role is Role.viewer


@pytest.mark.integration
@pytest.mark.security
def test_authenticate_rejects_deactivated_users_and_org_mismatches(
    auth: AuthService, db_session: Session, make_tenant: MakeTenant
) -> None:
    tenant, other = make_tenant(), make_tenant("globex")
    pair = auth.login(tenant.admin.email, PASSWORD)

    tenant.admin.is_active = False
    with pytest.raises(AuthenticationError):
        auth.authenticate(pair.access_token)
    tenant.admin.is_active = True

    tenant.admin.org_id = other.org.id  # token says org A, database says org B
    db_session.flush()
    with pytest.raises(AuthenticationError):
        auth.authenticate(pair.access_token)


@pytest.mark.integration
def test_authenticate_rejects_users_that_no_longer_exist(auth: AuthService) -> None:
    ghost = issue_access_token(
        user_id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        role=Role.admin,
        secret=SECRET,
        issuer="neo-orchestro",
        ttl=timedelta(minutes=5),
        now=datetime.now(UTC),
    )
    with pytest.raises(AuthenticationError):
        auth.authenticate(ghost)


# ------------------------------------------------------------------ change password


@pytest.mark.integration
@pytest.mark.security
def test_change_password_needs_the_old_one_and_revokes_all_sessions(
    auth: AuthService, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    me = principal_of(tenant.admin)
    pair = auth.login(tenant.admin.email, PASSWORD)

    with pytest.raises(AuthenticationError):
        auth.change_password(me, "not my password", "another long passphrase", CTX)
    with pytest.raises(ValidationFailedError):
        auth.change_password(me, PASSWORD, "short", CTX)

    auth.change_password(me, PASSWORD, "another long passphrase", CTX)
    with pytest.raises(AuthenticationError):
        auth.login(tenant.admin.email, PASSWORD)
    assert auth.login(tenant.admin.email, "another long passphrase").access_token
    with pytest.raises(AuthenticationError):  # the old session is gone
        auth.refresh(pair.refresh_token)
