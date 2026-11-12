"""Declarative base, naming conventions and shared column helpers."""

import enum
import uuid
from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, Enum, MetaData, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names => reviewable, reversible migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {
        uuid.UUID: PG_UUID(as_uuid=True),
        datetime: DateTime(timezone=True),
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


def uuid_pk() -> Mapped[uuid.UUID]:
    """UUID primary key generated in Python, with a server-side fallback for raw SQL."""
    return mapped_column(
        primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def created_at_column() -> Mapped[datetime]:
    """Insertion time. ``clock_timestamp()`` (not ``now()``) so it is real time, not txn start."""
    return mapped_column(server_default=func.clock_timestamp())


def str_enum(enum_cls: type[enum.StrEnum], name: str, length: int = 24) -> Enum:
    """Text-backed enum with a named CHECK constraint (no native PG enum, easy to migrate)."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
        values_callable=lambda e: [member.value for member in e],
    )
