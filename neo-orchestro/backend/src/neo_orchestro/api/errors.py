"""Uniform error envelope: ``{"error": {"code", "message", "details", "request_id"}}``.

Validation errors deliberately omit the submitted values (they may contain passwords).
"""

from http import HTTPStatus
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from neo_orchestro.core.errors import AppError

log = structlog.get_logger("neo_orchestro.api")

_HTTP_CODES = {
    401: "authentication_failed",
    403: "permission_denied",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    422: "validation_failed",
    429: "rate_limited",
}


def envelope(request: Request, code: str, message: str, details: Any = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": getattr(request.state, "request_id", None),
        }
    }


def _respond(
    request: Request, status: int, code: str, message: str, details: Any = None
) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(
        envelope(request, code, message, details), status_code=status, headers=headers
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return _respond(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        problems = [
            {"loc": [str(part) for part in err["loc"]], "msg": err["msg"], "type": err["type"]}
            for err in exc.errors()
        ]
        return _respond(
            request, 422, "validation_failed", "request validation failed", {"errors": problems}
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _HTTP_CODES.get(exc.status_code, "http_error")
        try:
            message = HTTPStatus(exc.status_code).phrase.lower()
        except ValueError:  # pragma: no cover - non-standard status
            message = "http error"
        return _respond(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error("http.unhandled_exception", exc_info=exc, path=request.url.path)
        return _respond(request, 500, "internal_error", "internal server error")
