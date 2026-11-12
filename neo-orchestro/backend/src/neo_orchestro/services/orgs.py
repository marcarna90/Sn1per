"""Organisation bootstrap (used by the CLI; there is deliberately no open sign-up endpoint)."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neo_orchestro.core.enums import AuditOutcome, Role
from neo_orchestro.core.errors import ConflictError
from neo_orchestro.core.security import hash_password, validate_password
from neo_orchestro.db.models import Organization, User
from neo_orchestro.repositories.auth import AuthRepository
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import RequestContext


def bootstrap_organization(
    session: Session,
    *,
    name: str,
    slug: str,
    admin_email: str,
    admin_password: str,
    context: RequestContext | None = None,
) -> tuple[Organization, User]:
    """Create an organisation together with its first administrator.

    Raises:
        ValidationFailedError: the password is weak.
        ConflictError: the slug or the e-mail address already exists.
    """
    email = admin_email.strip().lower()
    validate_password(admin_password, email=email)
    repo = AuthRepository(session)
    try:
        org = Organization(name=name, slug=slug)
        repo.add_organization(org)
        admin = User(
            org_id=org.id,
            email=email,
            password_hash=hash_password(admin_password),
            role=Role.admin,
        )
        repo.add_user(admin)
    except IntegrityError as exc:
        session.rollback()
        raise ConflictError("organisation slug or administrator e-mail already exists") from exc
    AuditService(session).record(
        action="org.bootstrap",
        outcome=AuditOutcome.success,
        org_id=org.id,
        actor_user_id=None,
        resource_type="organization",
        resource_id=org.id,
        context=context,
        details={"slug": slug, "admin_email": email},
    )
    session.commit()
    return org, admin
