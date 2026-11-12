"""Integration fixtures: a *real* PostgreSQL, migrated with Alembic.

Set ``NEO_TEST_DATABASE_URL`` to point at a disposable database (its ``public``
schema is dropped and recreated). Set ``NEO_REQUIRE_SERVICES=1`` (CI does) to make an
unreachable database a hard failure instead of a skip.
"""

import os
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

# Throw-away local development credentials; override with NEO_TEST_DATABASE_URL.
DEFAULT_TEST_URL = "postgresql+pg8000://neo:neo_dev_only@127.0.0.1:5432/neo_orchestro_test"
BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_database_url() -> str:
    return os.environ.get("NEO_TEST_DATABASE_URL", DEFAULT_TEST_URL)


def require_service(reason: str) -> None:
    if os.environ.get("NEO_REQUIRE_SERVICES"):
        pytest.fail(reason)
    pytest.skip(reason)


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    cfg.attributes["url"] = url
    return cfg


@pytest.fixture
def alembic_cfg() -> Callable[[str], Config]:
    """Factory building an Alembic config bound to a given database URL."""
    return alembic_config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = create_engine(test_database_url(), pool_pre_ping=True)
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        eng.dispose()
        require_service(f"PostgreSQL not reachable: {type(exc).__name__}")
    with eng.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(alembic_config(test_database_url()), "head")
    yield eng
    eng.dispose()


@pytest.fixture
def db_session(engine: Engine) -> Iterator[Session]:
    """A session whose work is rolled back at the end of each test."""
    connection = engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def scratch_db_url(engine: Engine) -> Iterator[str]:
    """An empty, throw-away database for migration tests."""
    base = make_url(test_database_url())
    name = f"neo_mig_{uuid.uuid4().hex[:12]}"
    admin = create_engine(base.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
