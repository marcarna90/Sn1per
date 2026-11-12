"""Authorised scope entries: the allowlist every scan is checked against (ADR 0004)."""

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, ForeignKey, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from neo_orchestro.core.enums import NetworkClass, ScopeKind
from neo_orchestro.db.base import Base, created_at_column, str_enum, uuid_pk


class ScopeEntry(Base):
    __tablename__ = "scope_entries"
    __table_args__ = (
        UniqueConstraint("org_id", "kind", "value", name="uq_scope_entries_org_kind_value"),
        CheckConstraint(
            "kind = 'domain' OR NOT include_subdomains", name="subdomains_only_for_domains"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ScopeKind] = mapped_column(str_enum(ScopeKind, "scope_kind", 16))
    # Normalised by the scope engine before storage (lowercase, IDNA, canonical CIDR).
    value: Mapped[str] = mapped_column(String(255))
    include_subdomains: Mapped[bool] = mapped_column(default=False, server_default=text("false"))
    network_class: Mapped[NetworkClass] = mapped_column(
        str_enum(NetworkClass, "scope_network_class", 16)
    )
    description: Mapped[str | None] = mapped_column(String(500), default=None)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    created_at: Mapped[datetime] = created_at_column()
