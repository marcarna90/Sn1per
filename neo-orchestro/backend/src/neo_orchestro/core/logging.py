"""Structured logging (structlog) with request correlation and secret redaction.

Standard-library loggers (uvicorn, celery, sqlalchemy) are routed through the
same pipeline so every line is uniformly structured and scrubbed.
"""

import logging
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog

_REDACTED = "[REDACTED]"
_SENSITIVE_FRAGMENTS = (
    "password",
    "passwd",
    "secret",
    "token",
    "authorization",
    "api_key",
    "apikey",
    "cookie",
    "credential",
    "private_key",
)
_HANDLER_TAG = "_neo_orchestro_handler"


def _is_sensitive(key: object) -> bool:
    lowered = str(key).lower()
    return any(fragment in lowered for fragment in _SENSITIVE_FRAGMENTS)


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (_REDACTED if _is_sensitive(k) else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_scrub(item) for item in value]
    return value


def scrub_mapping(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of ``data`` with sensitive values redacted (used before persisting details)."""
    return {k: (_REDACTED if _is_sensitive(k) else _scrub(v)) for k, v in data.items()}


def redact_secrets(
    _logger: object, _method: str, event_dict: MutableMapping[str, Any]
) -> MutableMapping[str, Any]:
    """structlog processor: replace values of sensitive keys, recursively."""
    for key in list(event_dict):
        if key != "event" and _is_sensitive(key):
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = _scrub(event_dict[key])
    return event_dict


def bind_request_id(request_id: str) -> None:
    """Attach a correlation id to every subsequent log line in this context."""
    structlog.contextvars.bind_contextvars(request_id=request_id)


def configure_logging(*, level: str = "INFO", json_logs: bool = False) -> None:
    """Configure structlog and the stdlib root logger. Idempotent."""
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        redact_secrets,
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    renderer: Any = (
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer(colors=False)
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            renderer,
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    setattr(handler, _HANDLER_TAG, True)

    root = logging.getLogger()
    for existing in [h for h in root.handlers if getattr(h, _HANDLER_TAG, False)]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
