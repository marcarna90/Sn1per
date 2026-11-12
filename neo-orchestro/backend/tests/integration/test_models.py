"""Model constraints enforced by the database itself (defence in depth)."""

import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from neo_orchestro.core.enums import (
    FindingCategory,
    NetworkClass,
    Role,
    ScanStatus,
    ScopeKind,
    Severity,
)
from neo_orchestro.db.models import Finding, Organization, ScanJob, ScopeEntry, User


def make_org(session: Session, slug: str = "acme") -> Organization:
    org = Organization(name=slug.title(), slug=slug)
    session.add(org)
    session.flush()
    return org


def make_user(session: Session, org: Organization, email: str = "a@example.com") -> User:
    user = User(org_id=org.id, email=email, password_hash="x", role=Role.analyst)
    session.add(user)
    session.flush()
    return user


def make_scan(session: Session, org: Organization, **kw: object) -> ScanJob:
    scan = ScanJob(org_id=org.id, engine="dns_recon", target="example.com", **kw)
    session.add(scan)
    session.flush()
    return scan


@pytest.mark.integration
def test_defaults_are_applied_by_the_database(db_session: Session) -> None:
    org = make_org(db_session)
    user = make_user(db_session, org)
    scan = make_scan(db_session, org)
    db_session.refresh(user)
    db_session.refresh(scan)
    assert isinstance(org.id, uuid.UUID)
    assert user.is_active is True
    assert user.failed_login_attempts == 0
    assert scan.status is ScanStatus.pending
    assert scan.attempts == 0
    assert scan.created_at is not None


@pytest.mark.integration
def test_enums_are_stored_as_readable_text(db_session: Session) -> None:
    org = make_org(db_session)
    make_user(db_session, org)
    stored = db_session.execute(text("SELECT role FROM users")).scalar_one()
    assert stored == "analyst"


@pytest.mark.integration
def test_email_is_unique_across_organisations(db_session: Session) -> None:
    make_user(db_session, make_org(db_session, "one"), "dup@example.com")
    other = make_org(db_session, "two")
    with pytest.raises(DBAPIError, match="uq_users_email"):
        make_user(db_session, other, "dup@example.com")
    db_session.rollback()


@pytest.mark.integration
def test_email_must_be_stored_lowercase(db_session: Session) -> None:
    org = make_org(db_session)
    with pytest.raises(DBAPIError, match="ck_users_email_lowercase"):
        make_user(db_session, org, "Mixed@Example.com")
    db_session.rollback()


@pytest.mark.integration
def test_slug_format_is_enforced(db_session: Session) -> None:
    with pytest.raises(DBAPIError, match="ck_organizations_slug_format"):
        make_org(db_session, "Not Valid!")
    db_session.rollback()


@pytest.mark.integration
def test_scope_entry_is_unique_per_organisation(db_session: Session) -> None:
    org = make_org(db_session)

    def entry() -> ScopeEntry:
        return ScopeEntry(
            org_id=org.id,
            kind=ScopeKind.domain,
            value="example.com",
            network_class=NetworkClass.external,
        )

    db_session.add(entry())
    db_session.flush()
    db_session.add(entry())
    with pytest.raises(DBAPIError, match="uq_scope_entries_org_kind_value"):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_subdomain_wildcard_only_applies_to_domains(db_session: Session) -> None:
    org = make_org(db_session)
    db_session.add(
        ScopeEntry(
            org_id=org.id,
            kind=ScopeKind.cidr,
            value="203.0.113.0/24",
            network_class=NetworkClass.external,
            include_subdomains=True,
        )
    )
    with pytest.raises(DBAPIError, match="ck_scope_entries_subdomains_only_for_domains"):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_unknown_scan_status_is_rejected_by_the_database(db_session: Session) -> None:
    org = make_org(db_session)
    make_scan(db_session, org)
    with pytest.raises(DBAPIError, match="ck_scans_scan_status"):
        db_session.execute(text("UPDATE scans SET status = 'exploded'"))
    db_session.rollback()


@pytest.mark.integration
def test_findings_are_deduplicated_per_scan(
    db_session: Session,
) -> None:
    org = make_org(db_session)
    scan = make_scan(db_session, org)

    def finding() -> Finding:
        return Finding(
            org_id=org.id,
            scan_id=scan.id,
            category=FindingCategory.dns_record,
            severity=Severity.info,
            title="A record",
            asset="example.com",
            fingerprint="f" * 64,
            source_engine="dns_recon",
        )

    db_session.add(finding())
    db_session.flush()
    db_session.add(finding())
    with pytest.raises(DBAPIError, match="uq_findings_scan_id_fingerprint"):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_deleting_a_scan_deletes_its_findings(db_session: Session) -> None:
    org = make_org(db_session)
    scan = make_scan(db_session, org)
    db_session.add(
        Finding(
            org_id=org.id,
            scan_id=scan.id,
            category=FindingCategory.info,
            severity=Severity.low,
            title="t",
            asset="example.com",
            fingerprint="a" * 64,
            source_engine="dns_recon",
        )
    )
    db_session.flush()
    db_session.execute(text("DELETE FROM scans WHERE id = :i"), {"i": scan.id})
    assert db_session.execute(select(Finding)).first() is None


@pytest.mark.integration
def test_an_organisation_with_users_cannot_be_deleted(db_session: Session) -> None:
    org = make_org(db_session)
    make_user(db_session, org)
    with pytest.raises(DBAPIError, match="fk_users_org_id_organizations"):
        db_session.execute(text("DELETE FROM organizations WHERE id = :i"), {"i": org.id})
    db_session.rollback()
