"""Audit trail writer. Never records secrets; callers commit with their own transaction."""

import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy.orm import Session

from neo_orchestro.core.enums import AuditOutcome, Role
from neo_orchestro.core.logging import scrub_mapping
from neo_orchestro.db.models import AuditLog
from neo_orchestro.repositories.audit import AuditReader, AuditRepository
from neo_orchestro.services.context import Principal, RequestContext, require_role


class AuditService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = AuditRepository(session)

    def list_for(
        self, principal: Principal, *, limit: int = 50, offset: int = 0, action: str | None = None
    ) -> list[AuditLog]:
        """The organisation's audit trail, newest first. Administrators only."""
        require_role(principal, Role.admin)
        return AuditReader(self._session, principal.org_id).list(
            limit=limit, offset=offset, action=action
        )

    def record(
        self,
        *,
        action: str,
        outcome: AuditOutcome,
        org_id: uuid.UUID | None = None,
        actor_user_id: uuid.UUID | None = None,
        resource_type: str | None = None,
        resource_id: str | uuid.UUID | None = None,
        context: RequestContext | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self._repo.add(
            AuditLog(
                action=action,
                outcome=outcome,
                org_id=org_id,
                actor_user_id=actor_user_id,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                ip=context.ip if context else None,
                request_id=context.request_id if context else None,
                details=scrub_mapping(dict(details or {})),
            )
        )

    def record_by(
        self,
        principal: Principal,
        *,
        action: str,
        outcome: AuditOutcome,
        resource_type: str | None = None,
        resource_id: str | uuid.UUID | None = None,
        context: RequestContext | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self.record(
            action=action,
            outcome=outcome,
            org_id=principal.org_id,
            actor_user_id=principal.user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            context=context,
            details=details,
        )
