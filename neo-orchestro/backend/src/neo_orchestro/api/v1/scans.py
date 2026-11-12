"""Scans: request, observe, cancel. Execution happens on workers (ADR 0007)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from neo_orchestro.api.deps import (
    ClockDep,
    ContextDep,
    DispatcherDep,
    PrincipalDep,
    RegistryDep,
    ResolverDep,
    SessionDep,
    SettingsDep,
    require,
)
from neo_orchestro.api.schemas import EngineOut, FindingOut, ScanCreate, ScanOut
from neo_orchestro.core.enums import Role, ScanStatus, Severity
from neo_orchestro.services.context import Principal
from neo_orchestro.services.scans import ScanService

router = APIRouter(tags=["scans"])
AnalystDep = Annotated[Principal, Depends(require(Role.analyst))]
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/engines", response_model=list[EngineOut], summary="Allowlisted scan engines")
def list_engines(
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    dispatcher: DispatcherDep,
) -> list[EngineOut]:
    engines = ScanService(session, principal, settings, registry, dispatcher).engines()
    return [
        EngineOut(
            name=e.name,
            description=e.description,
            target_kinds=sorted(e.target_kinds, key=lambda k: k.value),
        )
        for e in engines
    ]


@router.post(
    "/scans",
    response_model=ScanOut,
    status_code=202,
    summary="Request a scan (checked against the authorised scope, then queued)",
)
def create_scan(
    body: ScanCreate,
    response: Response,
    principal: AnalystDep,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    dispatcher: DispatcherDep,
    resolver: ResolverDep,
    clock: ClockDep,
    context: ContextDep,
) -> object:
    scan = ScanService(session, principal, settings, registry, dispatcher, clock=clock).create_scan(
        body.engine, body.target, body.params, resolver, context
    )
    response.headers["Location"] = f"/api/v1/scans/{scan.id}"
    return scan


@router.get("/scans", response_model=list[ScanOut], summary="List scans (newest first)")
def list_scans(
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    dispatcher: DispatcherDep,
    status: ScanStatus | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
) -> object:
    service = ScanService(session, principal, settings, registry, dispatcher)
    return service.list_scans(status=status, limit=limit, offset=offset)


@router.get("/scans/{scan_id}", response_model=ScanOut, summary="Get a scan")
def get_scan(
    scan_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    dispatcher: DispatcherDep,
) -> object:
    return ScanService(session, principal, settings, registry, dispatcher).get_scan(scan_id)


@router.get(
    "/scans/{scan_id}/findings",
    response_model=list[FindingOut],
    summary="Normalised findings of a scan",
)
def list_findings(
    scan_id: uuid.UUID,
    principal: PrincipalDep,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    dispatcher: DispatcherDep,
    severity: Severity | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Offset = 0,
) -> object:
    service = ScanService(session, principal, settings, registry, dispatcher)
    return service.list_findings(scan_id, severity=severity, limit=limit, offset=offset)


@router.post("/scans/{scan_id}/cancel", response_model=ScanOut, summary="Cancel a scan")
def cancel_scan(
    scan_id: uuid.UUID,
    principal: AnalystDep,
    session: SessionDep,
    settings: SettingsDep,
    registry: RegistryDep,
    dispatcher: DispatcherDep,
    clock: ClockDep,
    context: ContextDep,
) -> object:
    service = ScanService(session, principal, settings, registry, dispatcher, clock=clock)
    return service.cancel_scan(scan_id, context)
