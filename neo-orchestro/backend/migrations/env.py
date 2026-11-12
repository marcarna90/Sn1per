"""Alembic environment.

The URL is taken from ``config.attributes["url"]`` when provided (tests), otherwise
from application settings (``NEO_DATABASE_URL``). Logging is left to the application's
structlog configuration instead of ``fileConfig``.
"""

from alembic import context
from sqlalchemy import create_engine, pool

import neo_orchestro.db.models  # noqa: F401  (registers models on Base.metadata)
from neo_orchestro.core.config import get_settings
from neo_orchestro.db.base import Base

config = context.config
target_metadata = Base.metadata


def _database_url() -> str:
    override = config.attributes.get("url")
    if override:
        return str(override)
    return get_settings().database_url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
