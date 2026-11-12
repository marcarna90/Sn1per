"""Structured logging: JSON output, request correlation, secret redaction."""

import json

import pytest
import structlog

from neo_orchestro.core.logging import bind_request_id, configure_logging, redact_secrets


@pytest.mark.unit
def test_redacts_sensitive_keys_recursively() -> None:
    event = {
        "event": "login",
        "password": "hunter2",
        "Authorization": "Bearer abc",
        "nested": {"refresh_token": "xyz", "ok": 1},
        "items": [{"api_key": "k"}],
    }
    out = redact_secrets(None, "info", event)
    assert out["password"] == "[REDACTED]"
    assert out["Authorization"] == "[REDACTED]"
    assert out["nested"]["refresh_token"] == "[REDACTED]"
    assert out["nested"]["ok"] == 1
    assert out["items"][0]["api_key"] == "[REDACTED]"
    assert out["event"] == "login"


@pytest.mark.unit
def test_json_logs_carry_request_id_and_redact(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(level="INFO", json_logs=True)
    bind_request_id("req-123")
    structlog.get_logger("t").info("auth.login", user="a@example.com", password="hunter2")
    line = capsys.readouterr().out.strip().splitlines()[-1]
    data = json.loads(line)
    assert data["event"] == "auth.login"
    assert data["request_id"] == "req-123"
    assert data["password"] == "[REDACTED]"
    assert data["level"] == "info"
    assert "timestamp" in data
    structlog.contextvars.clear_contextvars()
