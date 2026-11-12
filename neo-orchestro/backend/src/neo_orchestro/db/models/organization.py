"""Organisation (tenant)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from neo_orchestro.db.base import Base, created_at_column, uuid_pk


class Organization(Base):
    """The tenant boundary: every other business row belongs to exactly one."""

    __tablename__ = "organizations"
    __table_args__ = (CheckConstraint("slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name="slug_format"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = created_at_column()
