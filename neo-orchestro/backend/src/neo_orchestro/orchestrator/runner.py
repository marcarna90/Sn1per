"""Scan execution on the worker side (ADR 0007).

``execute_scan`` is the only place a scan actually runs, and it is written so that Celery's
at-least-once delivery is safe:

1. **Atomic claim** — a conditional UPDATE moves ``pending|running`` to ``running`` and counts
   the attempt; finished, cancel-requested or over-retried scans are never (re)started.
2. **Scope re-validation** — the target is evaluated again *now* (fresh DNS, current rules),
   so rebinding or rule changes between request and execution stop the scan.
3. **Cooperative cancellation and a hard deadline** through ``EngineContext.check()``.
4. **Partial results are kept** (persisted in batches, de-duplicated by fingerprint, so a
   resumed scan does not duplicate findings).
5. **Errors are classified**: expected ones carry a stable code; anything unexpected is logged
   with its traceback but stored as a generic message, never leaking internals.
"""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import structlog
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import AuditOutcome, ScanStatus
from neo_orchestro.db.models import Finding, ScanJob
from neo_orchestro.engines import (
    Engine,
    EngineContext,
    EngineError,
    EngineRegistry,
    NormalisedFinding,
    ScanCancelled,
    UnknownEngineError,
)
from neo_orchestro.repositories.scans import WorkerScanRepository
from neo_orchestro.repositories.scope import ScopeRepository
from neo_orchestro.scope import Resolver, ScopeEngine, ScopeLimits, parse_target
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import Clock, utc_now
from neo_orchestro.services.scope import to_rules

log = structlog.get_logger("neo_orchestro.scans")

_BATCH_SIZE = 50
_MAX_MESSAGE = 500


@dataclass(frozen=True, slots=True)
class WorkerDeps:
    """Everything the runner needs, injected so it is testable without Celery or a network."""

    session_factory: Callable[[], Session]
    registry: EngineRegistry
    resolver: Resolver
    settings: Settings
    clock: Clock = utc_now
    poll_interval: float = 1.0  # seconds between cancellation checks
    max_findings: int = 10_000
    max_attempts: int = 3


def execute_scan(deps: WorkerDeps, scan_id: uuid.UUID) -> ScanStatus | None:
    """Run one scan. Returns its final status, or ``None`` if there was nothing to do
    (unknown id, or a redelivery for a scan that already finished)."""
    session = deps.session_factory()
    try:
        return _Execution(deps, session, scan_id).run()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()


class _Execution:
    def __init__(self, deps: WorkerDeps, session: Session, scan_id: uuid.UUID) -> None:
        self._deps = deps
        self._session = session
        self._scan_id = scan_id
        self._repo = WorkerScanRepository(session)
        self._audit = AuditService(session)
        self._findings_count = 0

    # ------------------------------------------------------------------ orchestration

    def run(self) -> ScanStatus | None:
        scan = self._repo.claim(self._scan_id, self._deps.clock(), self._deps.max_attempts)
        self._session.commit()  # publishes "running" and releases the row lock
        if scan is None:
            return self._without_claim()

        engine = self._resolve_engine(scan)
        if isinstance(engine, ScanStatus):
            return engine
        params_or_status = self._validate_params(scan, engine)
        if isinstance(params_or_status, ScanStatus):
            return params_or_status
        decision_or_status = self._revalidate_scope(scan, engine)
        if isinstance(decision_or_status, ScanStatus):
            return decision_or_status
        return self._run_engine(scan, engine, params_or_status, decision_or_status)

    def _without_claim(self) -> ScanStatus | None:
        scan = self._repo.get(self._scan_id)
        if scan is None or scan.status.is_terminal:
            return None  # redelivered message for a finished or unknown scan
        if scan.cancel_requested_at is not None:
            return self._finish(scan, ScanStatus.cancelled, AuditOutcome.success)
        if scan.attempts >= self._deps.max_attempts:
            return self._finish(
                scan,
                ScanStatus.failed,
                AuditOutcome.failure,
                code="max_attempts_exceeded",
                message="the scan was interrupted too many times and was abandoned",
            )
        return None

    # ------------------------------------------------------------------ pre-flight checks

    def _resolve_engine(self, scan: ScanJob) -> Engine | ScanStatus:
        try:
            return self._deps.registry.get(scan.engine)
        except UnknownEngineError:
            return self._finish(
                scan,
                ScanStatus.failed,
                AuditOutcome.denied,
                code="unknown_engine",
                message="the engine is not available",
            )

    def _validate_params(self, scan: ScanJob, engine: Engine) -> dict[str, object] | ScanStatus:
        try:
            return dict(engine.validate_params(scan.params))
        except EngineError as exc:
            return self._finish(
                scan, ScanStatus.failed, AuditOutcome.failure, code=exc.code, message=exc.message
            )

    def _revalidate_scope(self, scan: ScanJob, engine: Engine) -> tuple[str, ...] | ScanStatus:
        settings = self._deps.settings
        rules = to_rules(ScopeRepository(self._session, scan.org_id).list())
        limits = ScopeLimits(
            min_prefix_v4=settings.scope_min_prefix_v4, min_prefix_v6=settings.scope_min_prefix_v6
        )
        decision = ScopeEngine(rules, self._deps.resolver, limits=limits).evaluate(scan.target)
        scan.scope_decision = decision.to_dict()
        if not decision.allowed or decision.target is None:
            reason = decision.reason.value if decision.reason else "not_in_scope"
            return self._finish(
                scan,
                ScanStatus.failed,
                AuditOutcome.denied,
                code="scope_denied",
                message=f"target is no longer authorised ({reason})",
            )
        if parse_target(decision.target).kind not in engine.target_kinds:
            return self._finish(
                scan,
                ScanStatus.failed,
                AuditOutcome.failure,
                code="invalid_target",
                message="the engine does not accept this kind of target",
            )
        return decision.pinned_ips

    # ------------------------------------------------------------------ running

    def _run_engine(
        self,
        scan: ScanJob,
        engine: Engine,
        params: dict[str, object],
        pinned_ips: tuple[str, ...],
    ) -> ScanStatus:
        deps = self._deps
        scan_id, org_id, target = scan.id, scan.org_id, scan.target
        seen = self._repo.fingerprints(scan_id)  # non-empty when resuming after a crash
        ctx = EngineContext(
            scan_id=scan_id,
            target=target,
            pinned_ips=pinned_ips,
            params=params,
            is_cancelled=self._cancellation_poller(scan_id),
            deadline=time.monotonic() + deps.settings.scan_max_duration_seconds,
        )

        batch: list[Finding] = []
        status, code, message = ScanStatus.succeeded, None, None
        outcome = AuditOutcome.success
        try:
            for result in engine.run(ctx):
                if len(seen) >= deps.max_findings and result.fingerprint not in seen:
                    raise EngineError(
                        "too_many_findings", f"scan produced more than {deps.max_findings} findings"
                    )
                row = self._to_row(result, org_id, scan_id, engine.name)
                if row.fingerprint not in seen:
                    seen.add(row.fingerprint)
                    batch.append(row)
                if len(batch) >= _BATCH_SIZE:
                    self._persist(batch)
        except ScanCancelled:
            status = ScanStatus.cancelled
        except EngineError as exc:
            status, outcome = ScanStatus.failed, AuditOutcome.failure
            code, message = exc.code, exc.message[:_MAX_MESSAGE]
        except Exception:
            log.error(
                "scan.engine_crashed", scan_id=str(scan_id), engine=engine.name, exc_info=True
            )
            status, outcome = ScanStatus.failed, AuditOutcome.failure
            code, message = "internal_error", "an internal error interrupted the scan"
        self._persist(batch)  # partial results are kept on cancellation and failure
        return self._finish(scan, status, outcome, code=code, message=message)

    def _cancellation_poller(self, scan_id: uuid.UUID) -> Callable[[], bool]:
        state = {"last": 0.0, "cancelled": False}

        def poll() -> bool:
            if state["cancelled"]:
                return True
            now = time.monotonic()
            if now - state["last"] >= self._deps.poll_interval:
                state["last"] = now
                state["cancelled"] = bool(self._repo.cancel_requested(scan_id))
                self._session.commit()  # never sit idle inside a transaction
            return bool(state["cancelled"])

        return poll

    @staticmethod
    def _to_row(
        result: NormalisedFinding, org_id: uuid.UUID, scan_id: uuid.UUID, engine: str
    ) -> Finding:
        return Finding(
            org_id=org_id,
            scan_id=scan_id,
            category=result.category,
            severity=result.severity,
            title=result.title,
            asset=result.asset,
            description=result.description,
            evidence=result.evidence,
            fingerprint=result.fingerprint,
            source_engine=engine,
        )

    def _persist(self, batch: list[Finding]) -> None:
        if not batch:
            return
        self._repo.add_findings(batch)
        self._findings_count += len(batch)
        batch.clear()
        self._session.commit()

    # ------------------------------------------------------------------ finishing

    def _finish(
        self,
        scan: ScanJob,
        status: ScanStatus,
        outcome: AuditOutcome,
        *,
        code: str | None = None,
        message: str | None = None,
    ) -> ScanStatus:
        scan.status = status
        scan.finished_at = self._deps.clock()
        scan.error_code = code
        scan.error_message = message
        self._audit.record(
            action="scan.finish",
            outcome=outcome,
            org_id=scan.org_id,
            actor_user_id=scan.requested_by_id,
            resource_type="scan",
            resource_id=scan.id,
            details={"status": status.value, "findings": self._findings_count, "error_code": code},
        )
        self._session.commit()
        log.info("scan.finished", scan_id=str(scan.id), status=status.value, error_code=code)
        return status
