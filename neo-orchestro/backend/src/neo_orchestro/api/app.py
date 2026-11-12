"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from neo_orchestro import SIGNATURE, __version__
from neo_orchestro.api import health
from neo_orchestro.api.errors import register_exception_handlers
from neo_orchestro.api.metrics import Metrics
from neo_orchestro.api.middleware import RequestContextMiddleware
from neo_orchestro.api.v1 import router as v1_router
from neo_orchestro.core.config import Settings, get_settings
from neo_orchestro.core.logging import configure_logging
from neo_orchestro.db.session import create_db_engine, create_session_factory
from neo_orchestro.engines import default_registry
from neo_orchestro.orchestrator.dispatcher import CeleryDispatcher

_DESCRIPTION = (
    "Automated Security Assessment & Orchestration Platform. "
    f"{SIGNATURE}. Use only against systems you are authorised to test."
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)

    engine = create_db_engine(settings)  # connects lazily
    metrics = Metrics()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="Neo-Orchestro API",
        version=__version__,
        description=_DESCRIPTION,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.session_factory = create_session_factory(engine)
    app.state.metrics = metrics
    app.state.registry = default_registry(settings)  # the engine allowlist
    app.state.dispatcher = CeleryDispatcher(settings)  # connects lazily, on first publish

    if settings.cors_origins:  # closed by default; credentials only for listed origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Neo-CSRF"],
        )
    app.add_middleware(RequestContextMiddleware, metrics=metrics, hsts=settings.cookie_secure)
    register_exception_handlers(app)

    app.include_router(health.router)
    if settings.metrics_enabled:  # scrape endpoint: protect it at the reverse proxy
        app.add_api_route("/metrics", health.metrics, include_in_schema=False, tags=["ops"])
    app.include_router(v1_router, prefix="/api/v1")
    return app
