"""Scan persistence: a tenant-scoped repository for the API and an internal one for the worker."""

import uuid
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from neo_orchestro.core.enums import ScanStatus, Severity
from neo_orchestro.db.models import Finding, ScanJob
from neo_orchestro.repositories.base import TenantRepository


class ScanRepository(TenantRepository):
    def add(self, scan: ScanJob) -> None:
        scan.org_id = self._org_id
        self._session.add(scan)
        self._session.flush()

    def get(self, scan_id: uuid.UUID) -> ScanJob | None:
        return self._session.scalars(
            select(ScanJob).where(ScanJob.id == scan_id, ScanJob.org_id == self._org_id)
        ).one_or_none()

    def list_scans(self, *, status: ScanStatus | None, limit: int, offset: int) -> list[ScanJob]:
        query = select(ScanJob).where(ScanJob.org_id == self._org_id)
        if status is not None:
            query = query.where(ScanJob.status == status)
        return list(
            self._session.scalars(
                query.order_by(ScanJob.created_at.desc(), ScanJob.id.desc())
                .limit(limit)
                .offset(offset)
            )
        )

    def list_findings(
        self, scan_id: uuid.UUID, *, severity: Severity | None, limit: int, offset: int
    ) -> list[Finding]:
        query = select(Finding).where(Finding.scan_id == scan_id, Finding.org_id == self._org_id)
        if severity is not None:
            query = query.where(Finding.severity == severity)
        return list(
            self._session.scalars(
                query.order_by(Finding.created_at, Finding.id).limit(limit).offset(offset)
            )
        )

    def request_cancel(self, scan_id: uuid.UUID, now: datetime) -> None:
        """Cancel a queued scan outright, or flag a running one for cooperative stop.

        The queued->cancelled step is a conditional UPDATE so it can never overwrite a scan
        that a worker has just started.
        """
        cancelled_queued = self._session.execute(
            update(ScanJob)
            .where(
                ScanJob.id == scan_id,
                ScanJob.org_id == self._org_id,
                ScanJob.status == ScanStatus.pending,
            )
            .values(status=ScanStatus.cancelled, finished_at=now, cancel_requested_at=now)
            .returning(ScanJob.id)
        ).first()
        if cancelled_queued is None:
            self._session.execute(
                update(ScanJob)
                .where(
                    ScanJob.id == scan_id,
                    ScanJob.org_id == self._org_id,
                    ScanJob.status == ScanStatus.running,
                )
                .values(cancel_requested_at=now)
            )


class WorkerScanRepository:
    """Internal to the worker, which has no principal: it works by scan id and then uses the
    scan's own ``org_id`` for everything it touches. Never exposed to the API layer."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, scan_id: uuid.UUID) -> ScanJob | None:
        return self._session.get(ScanJob, scan_id, populate_existing=True)

    def claim(self, scan_id: uuid.UUID, now: datetime, max_attempts: int) -> ScanJob | None:
        """Atomically move a scan to ``running`` and count the attempt.

        Succeeds for ``pending`` (first delivery) and ``running`` (redelivery after a worker
        crash); never for finished or cancel-requested scans, nor beyond ``max_attempts``.
        """
        return self._session.scalars(
            update(ScanJob)
            .where(
                ScanJob.id == scan_id,
                ScanJob.status.in_([ScanStatus.pending, ScanStatus.running]),
                ScanJob.cancel_requested_at.is_(None),
                ScanJob.attempts < max_attempts,
            )
            .values(
                status=ScanStatus.running,
                started_at=func.coalesce(ScanJob.started_at, now),
                attempts=ScanJob.attempts + 1,
            )
            .returning(ScanJob)
            .execution_options(populate_existing=True)
        ).one_or_none()

    def cancel_requested(self, scan_id: uuid.UUID) -> bool:
        return (
            self._session.scalar(select(ScanJob.cancel_requested_at).where(ScanJob.id == scan_id))
            is not None
        )

    def fingerprints(self, scan_id: uuid.UUID) -> set[str]:
        return set(
            self._session.scalars(select(Finding.fingerprint).where(Finding.scan_id == scan_id))
        )

    def add_findings(self, findings: list[Finding]) -> None:
        self._session.add_all(findings)
        self._session.flush()
