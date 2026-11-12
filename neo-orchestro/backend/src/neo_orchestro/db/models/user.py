"""Users and refresh tokens."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from neo_orchestro.core.enums import Role
from neo_orchestro.db.base import Base, created_at_column, str_enum, uuid_pk


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lowercase"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    # Stored lowercase (enforced by CHECK); globally unique because login is by e-mail.
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(str_enum(Role, "user_role", 16))
    is_active: Mapped[bool] = mapped_column(default=True, server_default=text("true"))
    failed_login_attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(default=None)
    last_login_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = created_at_column()


class RefreshToken(Base):
    """Server-side record of an issued refresh token (rotation + reuse detection, ADR 0005).

    ``id`` is the token's ``jti``. All tokens descending from one login share a
    ``family_id`` so a replayed (already rotated) token revokes the whole family.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    family_id: Mapped[uuid.UUID] = mapped_column(index=True)
    expires_at: Mapped[datetime]
    revoked_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = created_at_column()
