"""Shared test helpers (importable thanks to ``pythonpath = ["src", "tests"]``)."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from neo_orchestro.db.models import Organization, User
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
