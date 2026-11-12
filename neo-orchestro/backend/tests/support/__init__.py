"""Shared test helpers (importable thanks to ``pythonpath = ["src", "tests"]``)."""

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from neo_orchestro.db.models import Organization, User
from neo_orchestro.scope import NoSuchDomainError
from neo_orchestro.services.context import Principal

PASSWORD = "correct horse battery"


class FakeClock:
    """Controllable time source injected into services."""

    def __init__(self) -> None:
        self.current = datetime.now(UTC)

    def __call__(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@dataclass
class Tenant:
    org: Organization
    admin: User
    password: str


def principal_of(user: User) -> Principal:
    return Principal(user_id=user.id, org_id=user.org_id, role=user.role, email=user.email)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class InMemoryDispatcher:
    """Records dispatched scan ids instead of publishing to a broker."""

    def __init__(self) -> None:
        self.ids: list[uuid.UUID] = []

    def enqueue(self, scan_id: uuid.UUID) -> str:
        self.ids.append(scan_id)
        return f"task-{len(self.ids)}"


class FakeDnsClient:
    """DNS client for dns_recon: a table of rdtype -> records (or an exception to raise)."""

    def __init__(self, table: Mapping[str, Any] | None = None) -> None:
        self.table: dict[str, Any] = dict(table or {})
        self.queries: list[tuple[str, str]] = []

    def query(self, name: str, rdtype: str) -> list[str]:
        self.queries.append((name, rdtype))
        answer = self.table.get(rdtype, [])
        if isinstance(answer, Exception):
            raise answer
        return list(answer)


class SharedSession:
    """Proxy around the test's savepoint session whose ``close()`` is a no-op.

    The runner opens (and closes) its own session per scan; in tests all work must stay
    inside the one rolled-back-at-the-end transaction, and ORM objects must stay attached.
    """

    def __init__(self, session: Any) -> None:
        self._session = session

    def __getattr__(self, name: str) -> Any:
        return getattr(self._session, name)

    def close(self) -> None:
        return None


class MutableResolver:
    """A resolver whose answers can change between calls (to simulate DNS rebinding)."""

    def __init__(self, table: dict[str, list[str]]) -> None:
        self.table = table

    def resolve(self, hostname: str) -> list[str]:
        try:
            return list(self.table[hostname])
        except KeyError:
            raise NoSuchDomainError(hostname) from None
