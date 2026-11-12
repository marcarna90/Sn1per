"""Alembic: the migration builds the schema, matches the models, and is reversible."""

from collections.abc import Callable

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from neo_orchestro.core.enums import AuditOutcome
from neo_orchestro.db.base import Base
from neo_orchestro.db.models import AuditLog

EXPECTED_TABLES = {
    "organizations",
    "users",
    "refresh_tokens",
    "scope_entries",
    "scans",
    "findings",
    "audit_logs",
}


@pytest.mark.integration
def test_upgrade_creates_the_expected_tables(
    scratch_db_url: str, alembic_cfg: Callable[[str], Config]
) -> None:
    command.upgrade(alembic_cfg(scratch_db_url), "head")
    engine = create_engine(scratch_db_url)
    try:
        assert set(inspect(engine).get_table_names()) == EXPECTED_TABLES | {"alembic_version"}
    finally:
        engine.dispose()


@pytest.mark.integration
def test_models_and_migration_are_in_sync(
    scratch_db_url: str, alembic_cfg: Callable[[str], Config]
) -> None:
    """If this fails, a model changed without a matching migration."""
    command.upgrade(alembic_cfg(scratch_db_url), "head")
    engine = create_engine(scratch_db_url)
    try:
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
        assert diff == []
    finally:
        engine.dispose()


@pytest.mark.integration
def test_downgrade_to_base_removes_everything(
    scratch_db_url: str, alembic_cfg: Callable[[str], Config]
) -> None:
    cfg = alembic_cfg(scratch_db_url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    engine = create_engine(scratch_db_url)
    try:
        assert set(inspect(engine).get_table_names()) == {"alembic_version"}
    finally:
        engine.dispose()


def _insert_audit_row(session: Session) -> None:
    session.add(AuditLog(action="auth.login", outcome=AuditOutcome.success, details={}))
    session.flush()


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_logs SET action = 'tampered'",
        "DELETE FROM audit_logs",
        "TRUNCATE audit_logs",
    ],
)
def test_audit_log_is_append_only(db_session: Session, statement: str) -> None:
    _insert_audit_row(db_session)
    with pytest.raises(DBAPIError, match="append-only"):
        db_session.execute(text(statement))
    db_session.rollback()
