"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-12 15:16:20.301769
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=True),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_id", sa.String(length=64), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "success",
                "denied",
                "failure",
                name="audit_outcome",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("ip", sa.String(length=45), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index(
        "ix_audit_logs_org_id_created_at", "audit_logs", ["org_id", "created_at"], unique=False
    )
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'", name=op.f("ck_organizations_slug_format")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name=op.f("uq_organizations_slug")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            sa.Enum(
                "viewer",
                "analyst",
                "admin",
                name="user_role",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "failed_login_attempts", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_users_org_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_org_id"), "users", ["org_id"], unique=False)
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("family_id", sa.UUID(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
    )
    op.create_index(
        op.f("ix_refresh_tokens_family_id"), "refresh_tokens", ["family_id"], unique=False
    )
    op.create_index(op.f("ix_refresh_tokens_user_id"), "refresh_tokens", ["user_id"], unique=False)
    op.create_table(
        "scans",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("requested_by_id", sa.UUID(), nullable=True),
        sa.Column("engine", sa.String(length=64), nullable=False),
        sa.Column("target", sa.String(length=255), nullable=False),
        sa.Column(
            "params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "running",
                "succeeded",
                "failed",
                "cancelled",
                name="scan_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("scope_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_scans_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_id"],
            ["users.id"],
            name=op.f("fk_scans_requested_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scans")),
    )
    op.create_index("ix_scans_org_id_created_at", "scans", ["org_id", "created_at"], unique=False)
    op.create_index("ix_scans_status", "scans", ["status"], unique=False)
    op.create_table(
        "scope_entries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum(
                "domain",
                "ip",
                "cidr",
                name="scope_kind",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("value", sa.String(length=255), nullable=False),
        sa.Column(
            "include_subdomains", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "network_class",
            sa.Enum(
                "external",
                "internal",
                name="scope_network_class",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_by_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind = 'domain' OR NOT include_subdomains",
            name=op.f("ck_scope_entries_subdomains_only_for_domains"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
            name=op.f("fk_scope_entries_created_by_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_scope_entries_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scope_entries")),
        sa.UniqueConstraint("org_id", "kind", "value", name="uq_scope_entries_org_kind_value"),
    )
    op.create_index(op.f("ix_scope_entries_org_id"), "scope_entries", ["org_id"], unique=False)
    op.create_table(
        "findings",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("org_id", sa.UUID(), nullable=False),
        sa.Column("scan_id", sa.UUID(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "asset",
                "dns_record",
                "open_port",
                "service",
                "vulnerability",
                "misconfiguration",
                "info",
                name="finding_category",
                native_enum=False,
                create_constraint=True,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.Enum(
                "info",
                "low",
                "medium",
                "high",
                "critical",
                name="finding_severity",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("asset", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("source_engine", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["org_id"],
            ["organizations.id"],
            name=op.f("fk_findings_org_id_organizations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["scan_id"], ["scans.id"], name=op.f("fk_findings_scan_id_scans"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_findings")),
        sa.UniqueConstraint("scan_id", "fingerprint", name="uq_findings_scan_id_fingerprint"),
    )
    op.create_index("ix_findings_org_id_severity", "findings", ["org_id", "severity"], unique=False)
    op.create_index(op.f("ix_findings_scan_id"), "findings", ["scan_id"], unique=False)

    # --- Hand-written: append-only audit log (ADR 0006) -------------------------------
    # Rejects UPDATE/DELETE (per row) and TRUNCATE (per statement). A DB owner can still
    # disable triggers; production must run the app with a role that does not own the table.
    op.execute(
        """
        CREATE FUNCTION audit_logs_reject_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: % is not allowed', TG_OP
                USING ERRCODE = 'restrict_violation';
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_update_delete
            BEFORE UPDATE OR DELETE ON audit_logs
            FOR EACH ROW EXECUTE FUNCTION audit_logs_reject_mutation()
        """
    )
    op.execute(
        """
        CREATE TRIGGER audit_logs_no_truncate
            BEFORE TRUNCATE ON audit_logs
            FOR EACH STATEMENT EXECUTE FUNCTION audit_logs_reject_mutation()
        """
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_findings_scan_id"), table_name="findings")
    op.drop_index("ix_findings_org_id_severity", table_name="findings")
    op.drop_table("findings")
    op.drop_index(op.f("ix_scope_entries_org_id"), table_name="scope_entries")
    op.drop_table("scope_entries")
    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_index("ix_scans_org_id_created_at", table_name="scans")
    op.drop_table("scans")
    op.drop_index(op.f("ix_refresh_tokens_user_id"), table_name="refresh_tokens")
    op.drop_index(op.f("ix_refresh_tokens_family_id"), table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index(op.f("ix_users_org_id"), table_name="users")
    op.drop_table("users")
    op.drop_table("organizations")
    op.drop_index("ix_audit_logs_org_id_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")  # also drops its triggers
    op.execute("DROP FUNCTION audit_logs_reject_mutation()")
