"""Operational endpoints (unversioned): liveness, readiness and Prometheus metrics."""

import redis
import structlog
from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import text

from neo_orchestro.api.deps import SessionDep, SettingsDep

router = APIRouter(tags=["ops"])
log = structlog.get_logger("neo_orchestro.health")


@router.get("/health/live", summary="Process is up")
def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", summary="Dependencies are reachable")
def ready(session: SessionDep, settings: SettingsDep) -> JSONResponse:
    checks = {"database": "ok", "redis": "ok"}
    try:
        session.execute(text("SELECT 1"))
    except Exception as exc:  # report failure, never details
        log.warning("health.database_unavailable", error=type(exc).__name__)
        checks["database"] = "fail"
    client = redis.Redis.from_url(
        settings.redis_url.get_secret_value(), socket_connect_timeout=1, socket_timeout=1
    )
    try:
        client.ping()
    except Exception as exc:
        log.warning("health.redis_unavailable", error=type(exc).__name__)
        checks["redis"] = "fail"
    finally:
        client.close()
    healthy = all(value == "ok" for value in checks.values())
    return JSONResponse(
        {"status": "ok" if healthy else "degraded", "checks": checks},
        status_code=200 if healthy else 503,
    )


def metrics(request: Request) -> Response:
    payload, content_type = request.app.state.metrics.render()
    return Response(payload, media_type=content_type)
