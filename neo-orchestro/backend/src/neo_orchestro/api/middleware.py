"""Request correlation, security headers, access log and metrics."""

import re
import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from neo_orchestro.api.metrics import UNMATCHED, Metrics
from neo_orchestro.core.logging import bind_request_id

log = structlog.get_logger("neo_orchestro.http")

_REQUEST_ID = re.compile(r"[A-Za-z0-9._-]{8,64}")
_DOC_PATHS = frozenset({"/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"})
_API_CSP = "default-src 'none'; frame-ancestors 'none'"


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, metrics: Metrics, hsts: bool) -> None:
        super().__init__(app)
        self._metrics = metrics
        self._hsts = hsts

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        inbound = request.headers.get("x-request-id", "")
        request_id = inbound if _REQUEST_ID.fullmatch(inbound) else uuid.uuid4().hex
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        bind_request_id(request_id)

        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started

        route = request.scope.get("route")
        route_label = getattr(route, "path", None) or UNMATCHED
        self._metrics.observe(request.method, route_label, response.status_code, elapsed)
        log.info(
            "http.request",
            method=request.method,
            route=route_label,
            status=response.status_code,
            duration_ms=round(elapsed * 1000, 1),
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        if request.url.path not in _DOC_PATHS:
            response.headers["Content-Security-Policy"] = _API_CSP
        if self._hsts:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
