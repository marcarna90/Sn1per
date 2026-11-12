"""User management (admin only) with last-administrator protection."""

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neo_orchestro.core.enums import AuditOutcome, Role
from neo_orchestro.core.errors import ConflictError, NotFoundError
from neo_orchestro.core.security import hash_password, validate_password
from neo_orchestro.db.models import User
from neo_orchestro.repositories.auth import AuthRepository
from neo_orchestro.repositories.users import UserRepository
from neo_orchestro.services.audit import AuditService
from neo_orchestro.services.context import (
    Clock,
    Principal,
    RequestContext,
    require_role,
    utc_now,
)


class UserService:
    def __init__(self, session: Session, principal: Principal, *, clock: Clock = utc_now) -> None:
        self._session = session
        self._principal = principal
        self._clock = clock
        self._users = UserRepository(session, principal.org_id)
        self._audit = AuditService(session)

    def create_user(
        self,
        *,
        email: str,
        password: str,
        role: Role,
        context: RequestContext | None = None,
    ) -> User:
        require_role(self._principal, Role.admin)
        email = email.strip().lower()
        validate_password(password, email=email)
        user = User(email=email, password_hash=hash_password(password), role=role)
        try:
            self._users.add(user)
        except IntegrityError as exc:
            self._session.rollback()
            raise ConflictError("a user with this e-mail already exists") from exc
        self._audit.record_by(
            self._principal,
            action="user.create",
            outcome=AuditOutcome.success,
            resource_type="user",
            resource_id=user.id,
            context=context,
            details={"email": email, "role": role.value},
        )
        self._session.commit()
        return user

    def list_users(self) -> list[User]:
        require_role(self._principal, Role.admin)
        return self._users.list()

    def get_user(self, user_id: uuid.UUID) -> User:
        require_role(self._principal, Role.admin)
        return self._get(user_id)

    def update_user(
        self,
        user_id: uuid.UUID,
        *,
        role: Role | None = None,
        is_active: bool | None = None,
        context: RequestContext | None = None,
    ) -> User:
        require_role(self._principal, Role.admin)
        user = self._get(user_id)

        removes_admin = (
            user.role is Role.admin
            and user.is_active
            and ((role is not None and role is not Role.admin) or is_active is False)
        )
        if removes_admin and self._users.count_active_admins() <= 1:
            raise ConflictError("cannot demote or deactivate the last active administrator")

        changes: dict[str, Any] = {}
        if role is not None and role is not user.role:
            user.role = role
            changes["role"] = role.value
        if is_active is not None and is_active is not user.is_active:
            user.is_active = is_active
            changes["is_active"] = is_active
            if not is_active:
                AuthRepository(self._session).revoke_user_tokens(user.id, self._clock())
        self._audit.record_by(
            self._principal,
            action="user.update",
            outcome=AuditOutcome.success,
            resource_type="user",
            resource_id=user.id,
            context=context,
            details=changes,
        )
        self._session.commit()
        return user

    def _get(self, user_id: uuid.UUID) -> User:
        user = self._users.get(user_id)
        if user is None:
            raise NotFoundError("user")  # also the answer for other tenants' users
        return user
