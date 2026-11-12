"""Application errors carry a stable machine code and an HTTP status."""

import pytest

from neo_orchestro.core.errors import (
    AppError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ScopeViolationError,
    ValidationFailedError,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("exc", "status", "code"),
    [
        (AuthenticationError("bad credentials"), 401, "authentication_failed"),
        (PermissionDeniedError("nope"), 403, "permission_denied"),
        (NotFoundError("scan"), 404, "not_found"),
        (ConflictError("exists"), 409, "conflict"),
        (ValidationFailedError("bad input"), 422, "validation_failed"),
        (ScopeViolationError("out of scope", reason="not_in_scope"), 403, "scope_violation"),
    ],
)
def test_error_status_and_code(exc: AppError, status: int, code: str) -> None:
    assert exc.status_code == status
    assert exc.code == code


@pytest.mark.unit
def test_scope_violation_exposes_reason_code() -> None:
    err = ScopeViolationError("blocked", reason="private_ip_not_authorised")
    assert err.details == {"reason": "private_ip_not_authorised"}


@pytest.mark.unit
def test_not_found_message_does_not_reveal_other_tenants() -> None:
    assert str(NotFoundError("scan")) == "scan not found"
