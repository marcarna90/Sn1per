"""Audit trail (administrators only)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from neo_orchestro.api.deps import SessionDep, require
from neo_orchestro.api.schemas import AuditLogOut
from neo_orchestro.core.enums import Role
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import Principal

router = APIRouter(prefix="/audit-logs", tags=["audit"])
AdminDep = Annotated[Principal, Depends(require(Role.admin))]


@router.get("", response_model=list[AuditLogOut], summary="Audit events of my organisation")
def list_audit_logs(
    principal: AdminDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    action: Annotated[str | None, Query(max_length=64)] = None,
) -> object:
    return AuditService(session).list_for(principal, limit=limit, offset=offset, action=action)
