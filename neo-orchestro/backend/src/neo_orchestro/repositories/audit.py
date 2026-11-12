"""Audit log access: a writer without tenant context and a tenant-scoped reader."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from neo_orchestro.db.models import AuditLog
from neo_orchestro.repositories.base import TenantRepository


class AuditRepository:
    """Insert-only. Events can precede tenant knowledge (e.g. a failed login), so no org here."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, entry: AuditLog) -> None:
        self._session.add(entry)
        self._session.flush()


class AuditReader(TenantRepository):
    def list(self, *, limit: int, offset: int, action: str | None = None) -> list[AuditLog]:
        query = select(AuditLog).where(AuditLog.org_id == self._org_id)
        if action:
            query = query.where(AuditLog.action == action)
        return list(
            self._session.scalars(query.order_by(AuditLog.id.desc()).limit(limit).offset(offset))
        )
