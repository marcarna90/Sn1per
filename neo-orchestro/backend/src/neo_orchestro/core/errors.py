"""Application error hierarchy.

Each error carries a stable machine-readable ``code`` and an HTTP status so the
API layer can render a uniform problem body without business logic leaking
into routers.
"""

from typing import Any


class AppError(Exception):
    """Base class for expected, user-visible errors."""

    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}


class AuthenticationError(AppError):
    status_code = 401
    code = "authentication_failed"


class PermissionDeniedError(AppError):
    status_code = 403
    code = "permission_denied"


class NotFoundError(AppError):
    """Also used for cross-tenant access so existence is never revealed (ADR 0006)."""

    status_code = 404
    code = "not_found"

    def __init__(self, resource: str) -> None:
        super().__init__(f"{resource} not found")


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ValidationFailedError(AppError):
    status_code = 422
    code = "validation_failed"


class ScopeViolationError(AppError):
    """A target is outside the organisation's authorised scope (ADR 0004)."""

    status_code = 403
    code = "scope_violation"

    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message, details={"reason": reason})


class ServiceUnavailableError(AppError):
    """A dependency (e.g. the task queue) is down; the request can be retried later."""

    status_code = 503
    code = "service_unavailable"
