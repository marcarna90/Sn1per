"""Scans and their normalised findings (ADR 0007, ADR 0008)."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from neo_orchestro.core.enums import FindingCategory, ScanStatus, Severity
from neo_orchestro.db.base import Base, created_at_column, str_enum, uuid_pk


class ScanJob(Base):
    """One scan request. Keeps who/what/when/how for every execution (governance)."""

    __tablename__ = "scans"
    __table_args__ = (
        Index("ix_scans_org_id_created_at", "org_id", "created_at"),
        Index("ix_scans_status", "status"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    requested_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), default=None
    )
    engine: Mapped[str] = mapped_column(String(64))
    target: Mapped[str] = mapped_column(String(255))
    params: Mapped[dict[str, Any]] = mapped_column(default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[ScanStatus] = mapped_column(
        str_enum(ScanStatus, "scan_status", 16),
        default=ScanStatus.pending,
        server_default=ScanStatus.pending.value,
    )
    error_code: Mapped[str | None] = mapped_column(String(64), default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    # Snapshot of the scope decision that authorised this run (matched entries, pinned IPs).
    scope_decision: Mapped[dict[str, Any] | None] = mapped_column(default=None)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(default=None)
    attempts: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    celery_task_id: Mapped[str | None] = mapped_column(String(64), default=None)
    created_at: Mapped[datetime] = created_at_column()
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)


class Finding(Base):
    """Engine-independent result record. Every engine maps its output to this shape."""

    __tablename__ = "findings"
    __table_args__ = (
        UniqueConstraint("scan_id", "fingerprint", name="uq_findings_scan_id_fingerprint"),
        Index("ix_findings_org_id_severity", "org_id", "severity"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    org_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    category: Mapped[FindingCategory] = mapped_column(
        str_enum(FindingCategory, "finding_category", 24)
    )
    severity: Mapped[Severity] = mapped_column(str_enum(Severity, "finding_severity", 16))
    title: Mapped[str] = mapped_column(String(300))
    asset: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    evidence: Mapped[dict[str, Any]] = mapped_column(
        default=dict, server_default=text("'{}'::jsonb")
    )
    fingerprint: Mapped[str] = mapped_column(String(64))
    source_engine: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = created_at_column()
