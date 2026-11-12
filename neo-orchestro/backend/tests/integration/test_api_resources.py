"""Users, scope and audit endpoints: happy paths, validation, conflicts."""

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from support import PASSWORD, Tenant, bearer

MakeTenant = Callable[..., Tenant]
Login = Callable[[str, str], str]


@pytest.fixture
def admin_headers(make_tenant: MakeTenant, login: Login) -> dict[str, str]:
    tenant = make_tenant()
    return bearer(login(tenant.admin.email, PASSWORD))


# ------------------------------------------------------------------ users


@pytest.mark.integration
def test_admin_manages_users(client: TestClient, admin_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={"email": "Analyst@Acme.Example.com", "password": PASSWORD, "role": "analyst"},
    )
    assert created.status_code == 201
    user = created.json()
    assert user["email"] == "analyst@acme.example.com"
    assert user["role"] == "analyst"
    assert user["is_active"] is True
    assert "password" not in str(user).lower()

    assert (
        client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={"email": "analyst@acme.example.com", "password": PASSWORD, "role": "viewer"},
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/users",
            headers=admin_headers,
            json={"email": "weak@acme.example.com", "password": "short", "role": "viewer"},
        ).status_code
        == 422
    )

    listing = client.get("/api/v1/users", headers=admin_headers).json()
    assert {u["email"] for u in listing} == {"admin@acme.example.com", "analyst@acme.example.com"}

    patched = client.patch(
        f"/api/v1/users/{user['id']}",
        headers=admin_headers,
        json={"role": "viewer", "is_active": False},
    )
    assert patched.status_code == 200
    assert (patched.json()["role"], patched.json()["is_active"]) == ("viewer", False)
    assert client.get(f"/api/v1/users/{user['id']}", headers=admin_headers).status_code == 200
    assert client.get(f"/api/v1/users/{uuid.uuid4()}", headers=admin_headers).status_code == 404


@pytest.mark.integration
@pytest.mark.security
def test_user_payloads_reject_unknown_and_dangerous_fields(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    body = {"email": "x@acme.example.com", "password": PASSWORD, "role": "viewer"}
    for extra in ({"org_id": str(uuid.uuid4())}, {"is_superuser": True}, {"password_hash": "x"}):
        assert (
            client.post("/api/v1/users", headers=admin_headers, json={**body, **extra}).status_code
            == 422
        )
    assert (
        client.post(
            "/api/v1/users", headers=admin_headers, json={**body, "role": "root"}
        ).status_code
        == 422
    )
    assert (
        client.patch(f"/api/v1/users/{uuid.uuid4()}", headers=admin_headers, json={}).status_code
        == 422
    )


@pytest.mark.integration
def test_the_last_admin_is_protected_over_the_api(
    client: TestClient, make_tenant: MakeTenant, login: Login
) -> None:
    tenant = make_tenant()
    headers = bearer(login(tenant.admin.email, PASSWORD))
    response = client.patch(
        f"/api/v1/users/{tenant.admin.id}", headers=headers, json={"role": "viewer"}
    )
    assert response.status_code == 409


# ------------------------------------------------------------------ scope


@pytest.mark.integration
def test_scope_entry_lifecycle(client: TestClient, admin_headers: dict[str, str]) -> None:
    created = client.post(
        "/api/v1/scope/entries",
        headers=admin_headers,
        json={
            "kind": "domain",
            "value": "App.Acme.Example.com.",
            "include_subdomains": True,
            "description": "prod",
        },
    )
    assert created.status_code == 201
    entry = created.json()
    assert (entry["value"], entry["include_subdomains"], entry["network_class"]) == (
        "app.acme.example.com",
        True,
        "external",
    )
    assert (
        client.post(
            "/api/v1/scope/entries",
            headers=admin_headers,
            json={"kind": "domain", "value": "app.acme.example.com", "include_subdomains": True},
        ).status_code
        == 409
    )

    assert [e["id"] for e in client.get("/api/v1/scope/entries", headers=admin_headers).json()] == [
        entry["id"]
    ]
    assert (
        client.delete(f"/api/v1/scope/entries/{entry['id']}", headers=admin_headers).status_code
        == 204
    )
    assert (
        client.delete(f"/api/v1/scope/entries/{entry['id']}", headers=admin_headers).status_code
        == 404
    )
    assert client.get("/api/v1/scope/entries", headers=admin_headers).json() == []


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("cidr", "0.0.0.0/0"),
        ("ip", "127.0.0.1"),
        ("ip", "169.254.169.254"),
        ("domain", "*.example.com"),
    ],
)
def test_dangerous_scope_entries_are_unprocessable(
    client: TestClient, admin_headers: dict[str, str], kind: str, value: str
) -> None:
    response = client.post(
        "/api/v1/scope/entries", headers=admin_headers, json={"kind": kind, "value": value}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


@pytest.mark.integration
def test_scope_check_returns_the_decision(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    client.post(
        "/api/v1/scope/entries",
        headers=admin_headers,
        json={"kind": "domain", "value": "acme.example.com", "include_subdomains": True},
    )

    ok = client.post(
        "/api/v1/scope/check", headers=admin_headers, json={"target": "app.acme.example.com"}
    )
    assert ok.status_code == 200
    assert ok.json()["allowed"] is True
    assert ok.json()["pinned_ips"] == ["93.184.216.34"]

    rebind = client.post(
        "/api/v1/scope/check", headers=admin_headers, json={"target": "evil.acme.example.com"}
    )
    assert rebind.json()["allowed"] is False
    assert rebind.json()["reason"] == "blocked_address"

    outside = client.post("/api/v1/scope/check", headers=admin_headers, json={"target": "evil.net"})
    assert (outside.status_code, outside.json()["reason"]) == (200, "not_in_scope")
    assert (
        client.post("/api/v1/scope/check", headers=admin_headers, json={"target": ""}).status_code
        == 422
    )


# ------------------------------------------------------------------ audit


@pytest.mark.integration
def test_audit_log_lists_the_organisations_events(
    client: TestClient, admin_headers: dict[str, str]
) -> None:
    client.post(
        "/api/v1/scope/entries",
        headers=admin_headers,
        json={"kind": "domain", "value": "acme.example.com"},
    )
    client.post("/api/v1/scope/check", headers=admin_headers, json={"target": "evil.net"})

    entries = client.get("/api/v1/audit-logs", headers=admin_headers).json()
    actions = [e["action"] for e in entries]
    assert {"org.bootstrap", "auth.login", "scope.create", "scope.check"} <= set(actions)
    assert entries == sorted(entries, key=lambda e: e["id"], reverse=True)  # newest first

    only = client.get(
        "/api/v1/audit-logs", headers=admin_headers, params={"action": "scope.check"}
    ).json()
    assert [e["action"] for e in only] == ["scope.check"]
    assert only[0]["outcome"] == "denied"

    page = client.get(
        "/api/v1/audit-logs", headers=admin_headers, params={"limit": 2, "offset": 1}
    ).json()
    assert len(page) == 2
    assert page[0]["id"] == entries[1]["id"]

    assert (
        client.get("/api/v1/audit-logs", headers=admin_headers, params={"limit": 1000}).status_code
        == 422
    )
    assert (
        client.get("/api/v1/audit-logs", headers=admin_headers, params={"limit": 0}).status_code
        == 422
    )
