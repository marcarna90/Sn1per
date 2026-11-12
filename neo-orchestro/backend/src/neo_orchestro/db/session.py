"""Engine and session factories. One session model shared by API and workers (ADR 0003)."""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from neo_orchestro.core.config import Settings, get_settings


def create_db_engine(settings: Settings) -> Engine:
    """Build an engine with a bounded pool and liveness checks."""
    return create_engine(
        settings.database_url.get_secret_value(),
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


@lru_cache
def get_engine() -> Engine:
    return create_db_engine(get_settings())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_engine())


@contextmanager
def session_scope(factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on any error."""
    session = (factory or get_session_factory())()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
