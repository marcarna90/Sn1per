"""Tenant-scoped user queries."""

import uuid

from sqlalchemy import func, select

from neo_orchestro.core.enums import Role
from neo_orchestro.db.models import User
from neo_orchestro.repositories.base import TenantRepository


class UserRepository(TenantRepository):
    def get(self, user_id: uuid.UUID) -> User | None:
        return self._session.scalars(
            select(User).where(User.id == user_id, User.org_id == self._org_id)
        ).one_or_none()

    def list(self) -> list[User]:
        return list(
            self._session.scalars(
                select(User).where(User.org_id == self._org_id).order_by(User.email)
            )
        )

    def add(self, user: User) -> None:
        user.org_id = self._org_id  # never trust a caller-supplied tenant
        self._session.add(user)
        self._session.flush()

    def count_active_admins(self) -> int:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(User)
                .where(
                    User.org_id == self._org_id, User.role == Role.admin, User.is_active.is_(True)
                )
            )
            or 0
        )
