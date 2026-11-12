"""Tenant-scoped scope-entry queries."""

import uuid

from sqlalchemy import select

from neo_orchestro.db.models import ScopeEntry
from neo_orchestro.repositories.base import TenantRepository


class ScopeRepository(TenantRepository):
    def list(self) -> list[ScopeEntry]:
        return list(
            self._session.scalars(
                select(ScopeEntry)
                .where(ScopeEntry.org_id == self._org_id)
                .order_by(ScopeEntry.created_at, ScopeEntry.value)
            )
        )

    def get(self, entry_id: uuid.UUID) -> ScopeEntry | None:
        return self._session.scalars(
            select(ScopeEntry).where(ScopeEntry.id == entry_id, ScopeEntry.org_id == self._org_id)
        ).one_or_none()

    def add(self, entry: ScopeEntry) -> None:
        entry.org_id = self._org_id
        self._session.add(entry)
        self._session.flush()

    def delete(self, entry: ScopeEntry) -> None:
        self._session.delete(entry)
        self._session.flush()
