"""Caller identity, request context, clock and role enforcement shared by services."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from neo_orchestro.core.enums import Role
from neo_orchestro.core.errors import PermissionDeniedError

Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Principal:
    """The authenticated caller. Role and organisation come from the database, not the token."""

    user_id: uuid.UUID
    org_id: uuid.UUID
    role: Role
    email: str


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Network metadata recorded in the audit trail."""

    ip: str | None = None
    request_id: str | None = None


def require_role(principal: Principal, minimum: Role) -> None:
    """Authoritative RBAC check (the API layer also checks early, this one cannot be bypassed)."""
    if not principal.role.at_least(minimum):
        raise PermissionDeniedError(f"requires role {minimum.value} or higher")
