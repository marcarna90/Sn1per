"""Cross-cutting API behaviour: health, headers, errors, docs, CORS, metrics."""

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from neo_orchestro import SIGNATURE, __version__
from neo_orchestro.api.app import create_app
from neo_orchestro.api.deps import get_session
from neo_orchestro.core.config import Settings


def variant(settings: Settings, **updates: Any) -> Settings:
    return settings.model_copy(update=updates)


# ------------------------------------------------------------------ health / meta


@pytest.mark.integration
def test_liveness_needs_no_dependencies(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.integration
def test_readiness_checks_database_and_redis(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "checks": {"database": "ok", "redis": "ok"}}


@pytest.mark.integration
def test_readiness_reports_a_down_redis_without_leaking_details(
    settings: Settings, db_session: Session
) -> None:
    application = create_app(variant(settings, redis_url=SecretStr("redis://127.0.0.1:1/0")))
    application.dependency_overrides[get_session] = lambda: db_session
    with TestClient(application) as test_client:
        response = test_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "degraded", "checks": {"database": "ok", "redis": "fail"}}


@pytest.mark.integration
def test_readiness_reports_a_down_database(settings: Settings) -> None:
    class BrokenSession:
        def execute(self, *_: object, **__: object) -> None:
            raise OperationalError("SELECT 1", {}, Exception("connection refused on 10.0.0.5"))

        def close(self) -> None: ...

    application = create_app(settings)
    application.dependency_overrides[get_session] = BrokenSession
    with TestClient(application) as test_client:
        response = test_client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "fail"
    assert "10.0.0.5" not in response.text


@pytest.mark.integration
def test_meta_carries_the_signature(client: TestClient) -> None:
    body = client.get("/api/v1/meta").json()
    assert body == {"name": "Neo-Orchestro", "version": __version__, "signature": SIGNATURE}
    assert body["signature"] == "Designed & Developed by Ronald TSR"


# ------------------------------------------------------------------ headers / request id


@pytest.mark.integration
@pytest.mark.security
def test_security_headers_are_set(client: TestClient) -> None:
    headers = client.get("/health/live").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"
    assert headers["content-security-policy"].startswith("default-src 'none'")
    assert "strict-transport-security" not in headers  # plain-HTTP dev


@pytest.mark.integration
@pytest.mark.security
def test_hsts_is_sent_when_cookies_are_secure(settings: Settings) -> None:
    application = create_app(variant(settings, cookie_secure=True))
    with TestClient(application) as test_client:
        hsts = test_client.get("/health/live").headers["strict-transport-security"]
    assert "max-age=" in hsts
    assert "includeSubDomains" in hsts


@pytest.mark.integration
def test_request_ids_are_generated_echoed_and_sanitised(client: TestClient) -> None:
    generated = client.get("/health/live").headers["x-request-id"]
    assert re.fullmatch(r"[0-9a-f]{32}", generated)

    assert (
        client.get("/health/live", headers={"X-Request-ID": "trace-abc-12345"}).headers[
            "x-request-id"
        ]
        == "trace-abc-12345"
    )

    hostile = client.get("/health/live", headers={"X-Request-ID": "bad id\r\nSet-Cookie: x=1"})
    assert re.fullmatch(r"[0-9a-f]{32}", hostile.headers["x-request-id"])
    assert "set-cookie" not in hostile.headers


# ------------------------------------------------------------------ errors


@pytest.mark.integration
def test_errors_use_one_envelope_with_the_request_id(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist", headers={"X-Request-ID": "trace-err-000001"})
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "not_found"
    assert error["request_id"] == "trace-err-000001"

    method = client.delete("/health/live")
    assert method.status_code == 405
    assert method.json()["error"]["code"] == "method_not_allowed"


@pytest.mark.integration
@pytest.mark.security
def test_validation_errors_never_echo_the_submitted_values(client: TestClient) -> None:
    secret = "SuperSecret-Password-12345"
    response = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": secret})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert secret not in response.text


@pytest.mark.integration
@pytest.mark.security
def test_unhandled_exceptions_are_hidden(app: Any) -> None:
    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "secret internal detail" not in response.text


# ------------------------------------------------------------------ docs / CORS / metrics


@pytest.mark.integration
@pytest.mark.security
def test_api_docs_are_off_in_production(settings: Settings) -> None:
    prod = variant(settings, env="production", cookie_secure=True, docs_enabled=False)
    with TestClient(create_app(prod)) as test_client:
        assert test_client.get("/docs").status_code == 404
        assert test_client.get("/openapi.json").status_code == 404


@pytest.mark.integration
def test_api_docs_are_served_in_development(client: TestClient) -> None:
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/openapi.json").json()["info"]["title"] == "Neo-Orchestro API"


@pytest.mark.integration
@pytest.mark.security
def test_cors_is_closed_by_default_and_open_only_for_listed_origins(settings: Settings) -> None:
    default = create_app(settings)
    with TestClient(default) as test_client:
        response = test_client.get("/health/live", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in response.headers

    configured = create_app(variant(settings, cors_origins=["https://ui.example.com"]))
    with TestClient(configured) as test_client:
        allowed = test_client.get("/health/live", headers={"Origin": "https://ui.example.com"})
        assert allowed.headers["access-control-allow-origin"] == "https://ui.example.com"
        assert allowed.headers["access-control-allow-credentials"] == "true"
        foreign = test_client.get("/health/live", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in foreign.headers


@pytest.mark.integration
def test_metrics_expose_request_counters_and_bounded_labels(client: TestClient) -> None:
    client.get("/health/live")
    client.get("/api/v1/nothing-here-1")
    client.get("/api/v1/nothing-here-2")
    text = client.get("/metrics").text
    assert "neo_http_requests_total" in text
    assert 'route="/health/live"' in text
    assert "nothing-here" not in text  # unknown paths must not create label cardinality
    assert 'route="unmatched"' in text


@pytest.mark.integration
def test_metrics_can_be_disabled(settings: Settings) -> None:
    with TestClient(create_app(variant(settings, metrics_enabled=False))) as test_client:
        assert test_client.get("/metrics").status_code == 404
