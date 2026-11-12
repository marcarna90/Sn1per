"""Append-only audit log (ADR 0006).

UPDATE, DELETE and TRUNCATE are rejected by database triggers created in the
initial migration; the application only ever INSERTs.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Identity, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from neo_orchestro.core.enums import AuditOutcome
from neo_orchestro.db.base import Base, created_at_column, str_enum


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_id_created_at", "org_id", "created_at"),
        Index("ix_audit_logs_action", "action"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    # Deliberately no foreign keys: the trail must outlive the rows it describes.
    org_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    action: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(64), default=None)
    resource_id: Mapped[str | None] = mapped_column(String(64), default=None)
    outcome: Mapped[AuditOutcome] = mapped_column(str_enum(AuditOutcome, "audit_outcome", 16))
    ip: Mapped[str | None] = mapped_column(String(45), default=None)
    request_id: Mapped[str | None] = mapped_column(String(64), default=None)
    details: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = created_at_column()
