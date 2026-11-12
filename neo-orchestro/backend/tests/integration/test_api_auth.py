"""Auth endpoints: cookies, CSRF header, rotation, logout, change-password."""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from neo_orchestro.api.app import create_app
from neo_orchestro.core.config import Settings
from support import PASSWORD, Tenant, bearer

MakeTenant = Callable[..., Tenant]
CSRF = {"X-Neo-CSRF": "1"}
COOKIE = "neo_refresh"


def set_refresh_cookie(client: TestClient, value: str) -> None:
    domain, path = "testserver.local", "/api/v1/auth"
    for cookie in list(client.cookies.jar):
        if cookie.name == COOKIE:
            domain, path = cookie.domain, cookie.path
    client.cookies.set(COOKIE, value, domain=domain, path=path)


def refresh_cookie(client: TestClient) -> str:
    value = client.cookies.get(COOKIE)
    assert value, "no refresh cookie in the jar"
    return value


@pytest.mark.integration
def test_login_returns_an_access_token_and_sets_the_refresh_cookie(
    client: TestClient, make_tenant: MakeTenant, settings: Settings
) -> None:
    tenant = make_tenant()
    response = client.post(
        "/api/v1/auth/login", json={"email": tenant.admin.email, "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"access_token", "token_type", "expires_in"}
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.access_token_ttl_minutes * 60
    assert "refresh" not in response.text.lower().replace("neo_refresh", "")  # not in the body

    [cookie] = [c for c in response.headers.get_list("set-cookie") if c.startswith(COOKIE)]
    lowered = cookie.lower()
    assert "httponly" in lowered
    assert "samesite=strict" in lowered
    assert "path=/api/v1/auth" in lowered
    assert f"max-age={settings.refresh_token_ttl_days * 86400}" in lowered
    assert "secure" not in lowered.replace("samesite", "")  # plain-HTTP test settings


@pytest.mark.integration
@pytest.mark.security
def test_the_cookie_is_secure_when_configured(
    settings: Settings, make_tenant: MakeTenant, app: Any
) -> None:
    tenant = make_tenant()
    secure_app = create_app(settings.model_copy(update={"cookie_secure": True}))
    secure_app.dependency_overrides = dict(app.dependency_overrides)
    with TestClient(secure_app) as test_client:
        response = test_client.post(
            "/api/v1/auth/login", json={"email": tenant.admin.email, "password": PASSWORD}
        )
    assert "; secure" in response.headers["set-cookie"].lower()


@pytest.mark.integration
@pytest.mark.security
def test_bad_credentials_are_indistinguishable(client: TestClient, make_tenant: MakeTenant) -> None:
    tenant = make_tenant()
    bodies = []
    for email, password in [
        (tenant.admin.email, "definitely wrong password"),
        ("ghost@nowhere.example.com", PASSWORD),
    ]:
        response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        body = response.json()
        body["error"].pop("request_id")
        bodies.append(body)
    assert bodies[0] == bodies[1]
    assert COOKIE not in client.cookies


@pytest.mark.integration
def test_unknown_fields_are_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "a@acme.example.com",
            "password": "x",
            "org_id": "11111111-1111-1111-1111-111111111111",
        },
    )
    assert response.status_code == 422


@pytest.mark.integration
def test_me_returns_the_caller(
    client: TestClient, make_tenant: MakeTenant, login: Callable[[str, str], str]
) -> None:
    tenant = make_tenant()
    token = login(tenant.admin.email, PASSWORD)
    body = client.get("/api/v1/auth/me", headers=bearer(token)).json()
    assert body["email"] == tenant.admin.email
    assert body["role"] == "admin"
    assert body["org_id"] == str(tenant.org.id)
    assert "password" not in str(body).lower()


@pytest.mark.integration
@pytest.mark.security
def test_refresh_requires_the_csrf_header_and_the_cookie(
    client: TestClient, make_tenant: MakeTenant, login: Callable[[str, str], str]
) -> None:
    tenant = make_tenant()
    assert client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401  # no cookie
    login(tenant.admin.email, PASSWORD)
    assert client.post("/api/v1/auth/refresh").status_code == 403  # cookie but no CSRF header
    assert client.post("/api/v1/auth/refresh", headers={"X-Neo-CSRF": "0"}).status_code == 403
    assert client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 200


@pytest.mark.integration
@pytest.mark.security
def test_refresh_rotates_the_cookie_and_replay_kills_the_session(
    client: TestClient, make_tenant: MakeTenant, login: Callable[[str, str], str]
) -> None:
    tenant = make_tenant()
    login(tenant.admin.email, PASSWORD)
    stolen = refresh_cookie(client)

    refreshed = client.post("/api/v1/auth/refresh", headers=CSRF)
    assert refreshed.status_code == 200
    current = refresh_cookie(client)
    assert current != stolen
    assert (
        client.get("/api/v1/auth/me", headers=bearer(refreshed.json()["access_token"])).status_code
        == 200
    )

    set_refresh_cookie(client, stolen)  # the thief replays the old cookie
    assert client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401
    set_refresh_cookie(client, current)  # and the victim's rotated cookie is dead as well
    assert client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401


@pytest.mark.integration
def test_logout_clears_the_cookie_and_revokes_the_session(
    client: TestClient, make_tenant: MakeTenant, login: Callable[[str, str], str]
) -> None:
    tenant = make_tenant()
    login(tenant.admin.email, PASSWORD)
    old = refresh_cookie(client)

    assert client.post("/api/v1/auth/logout").status_code == 403  # CSRF header required
    response = client.post("/api/v1/auth/logout", headers=CSRF)
    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()

    set_refresh_cookie(client, old)
    assert client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401
    assert client.post("/api/v1/auth/logout", headers=CSRF).status_code == 204  # idempotent


@pytest.mark.integration
@pytest.mark.security
def test_change_password_flow(
    client: TestClient, make_tenant: MakeTenant, login: Callable[[str, str], str]
) -> None:
    tenant = make_tenant()
    token = login(tenant.admin.email, PASSWORD)
    url = "/api/v1/auth/change-password"

    wrong = client.post(
        url,
        headers=bearer(token),
        json={"old_password": "nope nope nope!", "new_password": "another long passphrase"},
    )
    assert wrong.status_code == 401
    weak = client.post(
        url, headers=bearer(token), json={"old_password": PASSWORD, "new_password": "short"}
    )
    assert weak.status_code == 422
    assert (
        client.post(url, json={"old_password": PASSWORD, "new_password": "x" * 20}).status_code
        == 401
    )

    ok = client.post(
        url,
        headers=bearer(token),
        json={"old_password": PASSWORD, "new_password": "another long passphrase"},
    )
    assert ok.status_code == 204
    assert client.post("/api/v1/auth/refresh", headers=CSRF).status_code == 401  # sessions revoked
    bad = client.post(
        "/api/v1/auth/login", json={"email": tenant.admin.email, "password": PASSWORD}
    )
    assert bad.status_code == 401
    good = client.post(
        "/api/v1/auth/login",
        json={"email": tenant.admin.email, "password": "another long passphrase"},
    )
    assert good.status_code == 200
