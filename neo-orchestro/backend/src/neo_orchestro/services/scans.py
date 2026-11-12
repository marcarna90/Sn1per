"""Scan requests: allowlisted engines, scope pre-check, queueing, reading, cancelling."""

import uuid
from collections.abc import Mapping
from typing import Any, Protocol

from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome, Role, ScanStatus, Severity
from neo_orchestro.core.errors import (
    ConflictError,
    NotFoundError,
    ScopeViolationError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from neo_orchestro.db.models import Finding, ScanJob
from neo_orchestro.engines import Engine, EngineError, EngineRegistry, UnknownEngineError
from neo_orchestro.repositories.scans import ScanRepository
from neo_orchestro.scope import Resolver, parse_target
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import (
    Clock,
    Principal,
    RequestContext,
    require_role,
    utc_now,
)
from neo_orchestro.services.scope import ScopeService


class DispatchError(Exception):
    """The task queue refused or could not receive the scan."""


class ScanDispatcher(Protocol):
    def enqueue(self, scan_id: uuid.UUID) -> str:
        """Queue the scan for a worker; returns the queue's task id.

        Only the scan id travels through the broker: target and parameters are read from
        the database by the worker, so a poisoned queue cannot inject them.
        """
        ...


class ScanService:
    def __init__(
        self,
        session: Session,
        principal: Principal,
        settings: Settings,
        registry: EngineRegistry,
        dispatcher: ScanDispatcher,
        *,
        clock: Clock = utc_now,
    ) -> None:
        self._session = session
        self._principal = principal
        self._settings = settings
        self._registry = registry
        self._dispatcher = dispatcher
        self._clock = clock
        self._repo = ScanRepository(session, principal.org_id)
        self._scope = ScopeService(session, principal, settings)
        self._audit = AuditService(session)

    # ------------------------------------------------------------------ create

    def create_scan(
        self,
        engine_name: str,
        target: str,
        params: Mapping[str, Any] | None,
        resolver: Resolver,
        context: RequestContext | None = None,
    ) -> ScanJob:
        """Validate, authorise, persist and queue a scan.

        Raises:
            PermissionDeniedError: viewers cannot start scans.
            ValidationFailedError: unknown engine (not on the allowlist), bad parameters, or a
                target kind the engine does not accept.
            ScopeViolationError: the target is outside the authorised scope.
            ServiceUnavailableError: the task queue is down (the scan is recorded as failed).
        """
        require_role(self._principal, Role.analyst)
        engine = self._engine_or_deny(engine_name, context)
        try:
            validated = engine.validate_params(params or {})
        except EngineError as exc:
            self._deny(context, reason=exc.code, engine=engine.name)
            raise ValidationFailedError(exc.message) from exc

        decision = self._scope.engine(resolver).evaluate(target)
        if not decision.allowed or decision.target is None:
            reason = decision.reason.value if decision.reason else "not_in_scope"
            self._deny(context, reason=reason, engine=engine.name, target=target[:255])
            raise ScopeViolationError("target is not authorised for scanning", reason=reason)
        if parse_target(decision.target).kind not in engine.target_kinds:
            kinds = ", ".join(sorted(k.value for k in engine.target_kinds))
            self._deny(context, reason="target_kind", engine=engine.name, target=decision.target)
            raise ValidationFailedError(f"engine {engine.name} only accepts: {kinds}")

        scan = ScanJob(
            engine=engine.name,
            target=decision.target,
            params=validated,
            scope_decision=decision.to_dict(),
            requested_by_id=self._principal.user_id,
        )
        self._repo.add(scan)
        self._audit.record_by(
            self._principal,
            action="scan.create",
            outcome=AuditOutcome.success,
            resource_type="scan",
            resource_id=scan.id,
            context=context,
            details={"engine": engine.name, "target": decision.target},
        )
        self._session.commit()

        try:
            scan.celery_task_id = self._dispatcher.enqueue(scan.id)
        except DispatchError as exc:
            scan.status = ScanStatus.failed
            scan.error_code = "dispatch_failed"
            scan.error_message = "task queue unavailable"
            scan.finished_at = self._clock()
            self._session.commit()
            raise ServiceUnavailableError("task queue unavailable") from exc
        self._session.commit()
        return scan

    def _engine_or_deny(self, engine_name: str, context: RequestContext | None) -> Engine:
        try:
            return self._registry.get(engine_name)
        except UnknownEngineError:
            self._deny(context, reason="unknown_engine", engine=str(engine_name)[:60])
            raise ValidationFailedError("unknown engine") from None

    def _deny(self, context: RequestContext | None, **details: str) -> None:
        self._audit.record_by(
            self._principal,
            action="scan.create",
            outcome=AuditOutcome.denied,
            resource_type="scan",
            context=context,
            details=details,
        )
        self._session.commit()

    # ------------------------------------------------------------------ read

    def engines(self) -> list[Engine]:
        return self._registry.all()

    def list_scans(
        self, *, status: ScanStatus | None = None, limit: int = 50, offset: int = 0
    ) -> list[ScanJob]:
        return self._repo.list_scans(status=status, limit=limit, offset=offset)

    def get_scan(self, scan_id: uuid.UUID) -> ScanJob:
        scan = self._repo.get(scan_id)
        if scan is None:
            raise NotFoundError("scan")  # also the answer for other tenants' scans
        return scan

    def list_findings(
        self,
        scan_id: uuid.UUID,
        *,
        severity: Severity | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Finding]:
        self.get_scan(scan_id)  # 404 unless the scan belongs to this organisation
        return self._repo.list_findings(scan_id, severity=severity, limit=limit, offset=offset)

    # ------------------------------------------------------------------ cancel

    def cancel_scan(self, scan_id: uuid.UUID, context: RequestContext | None = None) -> ScanJob:
        require_role(self._principal, Role.analyst)
        scan = self.get_scan(scan_id)
        if scan.status.is_terminal:
            raise ConflictError("scan has already finished")
        self._repo.request_cancel(scan.id, self._clock())
        self._session.refresh(scan)
        self._audit.record_by(
            self._principal,
            action="scan.cancel",
            outcome=AuditOutcome.success,
            resource_type="scan",
            resource_id=scan.id,
            context=context,
            details={"status": scan.status.value},
        )
        self._session.commit()
        return scan
