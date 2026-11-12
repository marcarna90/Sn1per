"""Shared test configuration and fixtures.

Environment is prepared *before* any application module is imported so that `Settings`
never reads a developer's real `.env`.

Integration fixtures use a *real* PostgreSQL migrated with Alembic. Set
``NEO_TEST_DATABASE_URL`` to a disposable database (its ``public`` schema is dropped and
recreated). Set ``NEO_REQUIRE_SERVICES=1`` (CI does) so an unreachable service is a hard
failure instead of a skip.
"""

import os
import secrets
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from neo_orchestro.api.app import create_app
from neo_orchestro.api.deps import (
    get_clock,
    get_dispatcher,
    get_registry,
    get_resolver,
    get_session,
)
from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import Role
from neo_orchestro.db.models import User
from neo_orchestro.engines import DnsReconEngine, EngineRegistry
from neo_orchestro.scope import StaticResolver
from neo_orchestro.services.orgs import bootstrap_organization
from neo_orchestro.services.users import UserService
from support import PASSWORD, FakeClock, FakeDnsClient, InMemoryDispatcher, Tenant, principal_of

# Safe defaults so nothing ever reads a developer's real .env (explicit Settings are used in tests).
os.environ.setdefault("NEO_ENV", "test")
os.environ.setdefault("NEO_SECRET_KEY", secrets.token_urlsafe(48))

# Throw-away local development credentials; override with NEO_TEST_DATABASE_URL.
DEFAULT_TEST_URL = "postgresql+pg8000://neo:neo_dev_only@127.0.0.1:5432/neo_orchestro_test"
BACKEND_DIR = Path(__file__).resolve().parents[1]


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


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        env="test",
        secret_key="k" * 64,
        database_url=test_database_url(),
        redis_url=os.environ.get("NEO_TEST_REDIS_URL", "redis://127.0.0.1:6379/15"),
        login_max_failed_attempts=3,
        login_lockout_minutes=15,
    )


@pytest.fixture
def make_tenant(db_session: Session, settings: Settings) -> Callable[..., Tenant]:
    def _make(slug: str = "acme", email: str | None = None) -> Tenant:
        org, admin = bootstrap_organization(
            db_session,
            name=slug.title(),
            slug=slug,
            admin_email=email or f"admin@{slug}.example.com",
            admin_password=PASSWORD,
        )
        return Tenant(org=org, admin=admin, password=PASSWORD)

    return _make


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _make(tenant: Tenant, email: str, role: Role = Role.analyst) -> User:
        service = UserService(db_session, principal_of(tenant.admin))
        return service.create_user(email=email, password=PASSWORD, role=role)

    return _make


TEST_DNS: dict[str, list[str]] = {
    "app.acme.example.com": ["93.184.216.34"],
    "www.acme.example.com": ["93.184.216.34"],
    "evil.acme.example.com": ["127.0.0.1"],
}


@pytest.fixture
def dispatcher() -> InMemoryDispatcher:
    return InMemoryDispatcher()


@pytest.fixture
def api_registry() -> EngineRegistry:
    return EngineRegistry(
        [DnsReconEngine(FakeDnsClient({"A": ["93.184.216.34"], "TXT": ['"v=spf1 -all"']}))]
    )


@pytest.fixture
def app(
    settings: Settings,
    db_session: Session,
    clock: FakeClock,
    dispatcher: InMemoryDispatcher,
    api_registry: EngineRegistry,
) -> Any:
    application = create_app(settings)
    application.dependency_overrides[get_session] = lambda: db_session
    application.dependency_overrides[get_clock] = lambda: clock
    application.dependency_overrides[get_resolver] = lambda: StaticResolver(TEST_DNS)
    application.dependency_overrides[get_dispatcher] = lambda: dispatcher
    application.dependency_overrides[get_registry] = lambda: api_registry
    return application


@pytest.fixture
def client(app: Any) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def login(client: TestClient) -> Callable[[str, str], str]:
    """Log in via the real endpoint; returns the access token (the cookie stays in the jar)."""

    def _login(email: str, password: str = PASSWORD) -> str:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 200, response.text
        return str(response.json()["access_token"])

    return _login
