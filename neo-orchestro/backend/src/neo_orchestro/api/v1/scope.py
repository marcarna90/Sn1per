"""Authorised scope: the allowlist every scan is checked against."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response

from neo_orchestro.api.deps import (
    ContextDep,
    PrincipalDep,
    ResolverDep,
    SessionDep,
    SettingsDep,
    require,
)
from neo_orchestro.api.schemas import (
    DecisionOut,
    ScopeCheckRequest,
    ScopeEntryCreate,
    ScopeEntryOut,
)
from neo_orchestro.core.enums import Role
from neo_orchestro.services.context import Principal
from neo_orchestro.services.scope import ScopeService

router = APIRouter(prefix="/scope", tags=["scope"])
AdminDep = Annotated[Principal, Depends(require(Role.admin))]
AnalystDep = Annotated[Principal, Depends(require(Role.analyst))]


@router.get("/entries", response_model=list[ScopeEntryOut], summary="List authorised scope")
def list_entries(principal: PrincipalDep, session: SessionDep, settings: SettingsDep) -> object:
    return ScopeService(session, principal, settings).list_entries()


@router.post(
    "/entries",
    response_model=ScopeEntryOut,
    status_code=201,
    summary="Authorise a domain, IP or CIDR",
)
def add_entry(
    body: ScopeEntryCreate,
    principal: AdminDep,
    session: SessionDep,
    settings: SettingsDep,
    context: ContextDep,
) -> object:
    return ScopeService(session, principal, settings).add_entry(
        body.kind,
        body.value,
        include_subdomains=body.include_subdomains,
        description=body.description,
        context=context,
    )


@router.delete("/entries/{entry_id}", status_code=204, summary="Remove an authorisation")
def delete_entry(
    entry_id: uuid.UUID,
    principal: AdminDep,
    session: SessionDep,
    settings: SettingsDep,
    context: ContextDep,
) -> Response:
    ScopeService(session, principal, settings).delete_entry(entry_id, context)
    return Response(status_code=204)


@router.post("/check", response_model=DecisionOut, summary="Dry-run: would this target be allowed?")
def check_target(
    body: ScopeCheckRequest,
    principal: AnalystDep,
    session: SessionDep,
    settings: SettingsDep,
    resolver: ResolverDep,
    context: ContextDep,
) -> DecisionOut:
    decision = ScopeService(session, principal, settings).check(body.target, resolver, context)
    return DecisionOut.model_validate(decision.to_dict())
