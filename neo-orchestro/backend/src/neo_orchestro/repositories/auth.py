"""Repository for the authentication flow.

This is the **only** repository allowed to look across organisations: at login and token
validation time the tenant is not known yet. It exposes nothing but identity primitives.
"""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from neo_orchestro.db.models import Organization, RefreshToken, User


class AuthRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_user_by_email(self, email: str) -> User | None:
        return self._session.scalars(select(User).where(User.email == email)).one_or_none()

    def get_user(self, user_id: uuid.UUID) -> User | None:
        return self._session.get(User, user_id)

    def add_organization(self, org: Organization) -> None:
        self._session.add(org)
        self._session.flush()

    def add_user(self, user: User) -> None:
        self._session.add(user)
        self._session.flush()

    def add_refresh_token(self, token: RefreshToken) -> None:
        self._session.add(token)
        self._session.flush()

    def get_refresh_token(self, jti: uuid.UUID) -> RefreshToken | None:
        return self._session.get(RefreshToken, jti)

    def get_refresh_token_for_update(self, jti: uuid.UUID) -> RefreshToken | None:
        """Row-locked read: concurrent refreshes of one token are serialised."""
        return self._session.scalars(
            select(RefreshToken).where(RefreshToken.id == jti).with_for_update()
        ).one_or_none()

    def revoke_family(self, family_id: uuid.UUID, now: datetime) -> int:
        """Revoke every live token of a family; returns how many were still alive."""
        revoked = self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
            .returning(RefreshToken.id)
        )
        return len(revoked.all())

    def revoke_user_tokens(self, user_id: uuid.UUID, now: datetime) -> None:
        self._session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
