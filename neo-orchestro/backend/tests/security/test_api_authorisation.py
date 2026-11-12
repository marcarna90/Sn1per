"""RBAC matrix, tenant isolation and token attacks, exercised through the real HTTP API."""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import Role, ScopeKind
from neo_orchestro.core.security import issue_access_token, issue_refresh_token
from neo_orchestro.db.models import User
from neo_orchestro.services.scope import ScopeService
from support import PASSWORD, Tenant, bearer, principal_of

MakeTenant = Callable[..., Tenant]
MakeUser = Callable[..., User]
Login = Callable[[str, str], str]
SECRET = "k" * 64
RANDOM_ID = str(uuid.uuid4())

# (method, path, json body, expected status per role)
MATRIX: list[tuple[str, str, dict[str, Any] | None, dict[str, int]]] = [
    ("GET", "/api/v1/auth/me", None, {"viewer": 200, "analyst": 200, "admin": 200}),
    ("GET", "/api/v1/users", None, {"viewer": 403, "analyst": 403, "admin": 200}),
    (
        "POST",
        "/api/v1/users",
        {"email": "new@acme.example.com", "password": PASSWORD, "role": "viewer"},
        {"viewer": 403, "analyst": 403, "admin": 201},
    ),
    ("GET", f"/api/v1/users/{RANDOM_ID}", None, {"viewer": 403, "analyst": 403, "admin": 404}),
    (
        "PATCH",
        f"/api/v1/users/{RANDOM_ID}",
        {"role": "viewer"},
        {"viewer": 403, "analyst": 403, "admin": 404},
    ),
    ("GET", "/api/v1/scope/entries", None, {"viewer": 200, "analyst": 200, "admin": 200}),
    (
        "POST",
        "/api/v1/scope/entries",
        {"kind": "domain", "value": "x.acme.example.com"},
        {"viewer": 403, "analyst": 403, "admin": 201},
    ),
    (
        "DELETE",
        f"/api/v1/scope/entries/{RANDOM_ID}",
        None,
        {"viewer": 403, "analyst": 403, "admin": 404},
    ),
    (
        "POST",
        "/api/v1/scope/check",
        {"target": "app.acme.example.com"},
        {"viewer": 403, "analyst": 200, "admin": 200},
    ),
    ("GET", "/api/v1/audit-logs", None, {"viewer": 403, "analyst": 403, "admin": 200}),
    ("GET", "/api/v1/engines", None, {"viewer": 200, "analyst": 200, "admin": 200}),
    ("GET", "/api/v1/scans", None, {"viewer": 200, "analyst": 200, "admin": 200}),
    (
        "POST",
        "/api/v1/scans",
        {"engine": "dns_recon", "target": "app.acme.example.com"},
        {"viewer": 403, "analyst": 202, "admin": 202},
    ),
    ("GET", f"/api/v1/scans/{RANDOM_ID}", None, {"viewer": 404, "analyst": 404, "admin": 404}),
    (
        "GET",
        f"/api/v1/scans/{RANDOM_ID}/findings",
        None,
        {"viewer": 404, "analyst": 404, "admin": 404},
    ),
    (
        "POST",
        f"/api/v1/scans/{RANDOM_ID}/cancel",
        None,
        {"viewer": 403, "analyst": 404, "admin": 404},
    ),
]


def ids(case: tuple[Any, ...]) -> str:
    return f"{case[0]} {case[1].replace(RANDOM_ID, '{id}')}"


@pytest.mark.security
@pytest.mark.integration
@pytest.mark.parametrize("role", ["viewer", "analyst", "admin"])
@pytest.mark.parametrize("case", MATRIX, ids=ids)
def test_rbac_matrix(
    client: TestClient,
    db_session: Session,
    settings: Settings,
    make_tenant: MakeTenant,
    make_user: MakeUser,
    login: Login,
    case: tuple[str, str, dict[str, Any] | None, dict[str, int]],
    role: str,
) -> None:
    method, path, body, expected = case
    tenant = make_tenant()
    ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
        ScopeKind.domain, "acme.example.com", include_subdomains=True
    )  # so POST /scans exercises RBAC, not the scope check
    user = make_user(tenant, f"{role}-user@acme.example.com", Role(role))
    response = client.request(method, path, json=body, headers=bearer(login(user.email, PASSWORD)))
    assert response.status_code == expected[role], response.text


@pytest.mark.security
@pytest.mark.integration
@pytest.mark.parametrize("case", MATRIX, ids=ids)
def test_every_endpoint_requires_authentication(
    client: TestClient, case: tuple[str, str, dict[str, Any] | None, dict[str, int]]
) -> None:
    method, path, body, _ = case
    response = client.request(method, path, json=body)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


# ------------------------------------------------------------------ tenant isolation


@pytest.mark.security
@pytest.mark.integration
def test_one_organisation_cannot_see_or_touch_anothers_data(
    client: TestClient,
    db_session: Session,
    make_tenant: MakeTenant,
    make_user: MakeUser,
    settings: Any,
    login: Login,
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    victim = make_user(globex, "victim@globex.example.com")
    entry = ScopeService(db_session, principal_of(globex.admin), settings).add_entry(
        ScopeKind.domain, "app.acme.example.com"
    )
    headers = bearer(login(acme.admin.email, PASSWORD))

    # Lists show only my organisation.
    assert [u["email"] for u in client.get("/api/v1/users", headers=headers).json()] == [
        acme.admin.email
    ]
    assert client.get("/api/v1/scope/entries", headers=headers).json() == []
    audit = client.get("/api/v1/audit-logs", headers=headers).json()
    assert audit
    assert all(e["actor_user_id"] in (None, str(acme.admin.id)) for e in audit)

    # Direct access by id answers 404, exactly like a non-existent id (no existence oracle).
    other_user = client.get(f"/api/v1/users/{victim.id}", headers=headers)
    missing_user = client.get(f"/api/v1/users/{uuid.uuid4()}", headers=headers)
    assert other_user.status_code == missing_user.status_code == 404
    assert other_user.json()["error"]["code"] == missing_user.json()["error"]["code"]
    assert (
        client.patch(
            f"/api/v1/users/{victim.id}", headers=headers, json={"role": "admin"}
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/scope/entries/{entry.id}", headers=headers).status_code == 404

    # Their rules do not authorise my scans: the same name is out of scope for me.
    check = client.post(
        "/api/v1/scope/check", headers=headers, json={"target": "app.acme.example.com"}
    )
    assert check.json()["reason"] == "not_in_scope"

    db_session.refresh(victim)
    assert victim.role is Role.analyst


@pytest.mark.security
@pytest.mark.integration
def test_the_tenant_can_never_be_chosen_by_the_client(
    client: TestClient, make_tenant: MakeTenant, login: Login
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    headers = bearer(login(acme.admin.email, PASSWORD))
    for path, body in [
        ("/api/v1/users", {"email": "z@x.example.com", "password": PASSWORD, "role": "viewer"}),
        ("/api/v1/scope/entries", {"kind": "domain", "value": "z.example.com"}),
    ]:
        smuggled = client.post(path, headers=headers, json={**body, "org_id": str(globex.org.id)})
        assert smuggled.status_code == 422
    assert (
        client.get("/api/v1/users", headers={**headers, "X-Org-ID": str(globex.org.id)}).json()[0][
            "email"
        ]
        == acme.admin.email
    )


# ------------------------------------------------------------------ token attacks


@pytest.mark.security
@pytest.mark.integration
@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Bearer",
        "Bearer ",
        "Bearer garbage",
        "Basic YWRtaW46YWRtaW4=",
        "bearer",
        "Token abc",
    ],
)
def test_malformed_credentials_are_rejected(client: TestClient, authorization: str | None) -> None:
    headers = {} if authorization is None else {"Authorization": authorization}
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


@pytest.mark.security
@pytest.mark.integration
def test_forged_expired_and_cross_type_tokens_are_rejected(
    client: TestClient, make_tenant: MakeTenant
) -> None:
    tenant = make_tenant()
    common: dict[str, Any] = {
        "user_id": tenant.admin.id,
        "org_id": tenant.org.id,
        "role": Role.admin,
    }

    def access(**kw: Any) -> str:
        return issue_access_token(
            **{
                **common,
                "secret": SECRET,
                "issuer": "neo-orchestro",
                "ttl": timedelta(minutes=5),
                **kw,
            }
        )

    me = "/api/v1/auth/me"
    assert client.get(me, headers=bearer(access())).status_code == 200  # control: a valid one works
    assert client.get(me, headers=bearer(access(secret="x" * 64))).status_code == 401  # wrong key
    assert client.get(me, headers=bearer(access(issuer="evil"))).status_code == 401
    expired = access(now=datetime.now(UTC) - timedelta(hours=2))
    assert client.get(me, headers=bearer(expired)).status_code == 401
    refresh = issue_refresh_token(
        user_id=tenant.admin.id,
        jti=uuid.uuid4(),
        family_id=uuid.uuid4(),
        secret=SECRET,
        issuer="neo-orchestro",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    assert client.get(me, headers=bearer(refresh)).status_code == 401  # refresh used as access


@pytest.mark.security
@pytest.mark.integration
def test_a_token_claiming_another_organisation_is_rejected(
    client: TestClient, make_tenant: MakeTenant
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    forged = issue_access_token(
        user_id=acme.admin.id,
        org_id=globex.org.id,  # valid signature, but the claim contradicts the database
        role=Role.admin,
        secret=SECRET,
        issuer="neo-orchestro",
        ttl=timedelta(minutes=5),
    )
    assert client.get("/api/v1/users", headers=bearer(forged)).status_code == 401


@pytest.mark.security
@pytest.mark.integration
def test_deactivation_and_demotion_take_effect_immediately(
    client: TestClient, make_tenant: MakeTenant, make_user: MakeUser, login: Login
) -> None:
    tenant = make_tenant()
    other_admin = make_user(tenant, "boss@acme.example.com", Role.admin)
    token = login(other_admin.email, PASSWORD)
    assert client.get("/api/v1/users", headers=bearer(token)).status_code == 200

    other_admin.role = Role.viewer  # demoted: the still-valid token must lose its privileges
    assert client.get("/api/v1/users", headers=bearer(token)).status_code == 403
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200

    other_admin.is_active = False  # deactivated: the still-valid token is dead
    assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


@pytest.mark.security
@pytest.mark.integration
def test_the_lockout_applies_over_http(client: TestClient, make_tenant: MakeTenant) -> None:
    tenant = make_tenant()
    for _ in range(3):
        bad = client.post(
            "/api/v1/auth/login",
            json={"email": tenant.admin.email, "password": "wrong wrong wrong"},
        )
        assert bad.status_code == 401
    locked = client.post(
        "/api/v1/auth/login", json={"email": tenant.admin.email, "password": PASSWORD}
    )
    assert locked.status_code == 401  # even the right password


@pytest.mark.security
@pytest.mark.integration
def test_scans_are_isolated_between_organisations(
    client: TestClient,
    db_session: Session,
    settings: Settings,
    make_tenant: MakeTenant,
    login: Login,
) -> None:
    acme, globex = make_tenant("acme"), make_tenant("globex")
    for tenant, domain in ((acme, "acme.example.com"), (globex, "globex.example.com")):
        ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
            ScopeKind.domain, domain, include_subdomains=True
        )
    acme_headers = bearer(login(acme.admin.email, PASSWORD))
    mine = client.post(
        "/api/v1/scans",
        headers=acme_headers,
        json={"engine": "dns_recon", "target": "app.acme.example.com"},
    ).json()["id"]
    globex_headers = bearer(login(globex.admin.email, PASSWORD))

    assert client.get("/api/v1/scans", headers=globex_headers).json() == []
    for method, path in [
        ("GET", f"/api/v1/scans/{mine}"),
        ("GET", f"/api/v1/scans/{mine}/findings"),
        ("POST", f"/api/v1/scans/{mine}/cancel"),
    ]:
        assert client.request(method, path, headers=globex_headers).status_code == 404, path
    # Globex cannot scan Acme's domain either: it is not in *their* scope.
    theirs = client.post(
        "/api/v1/scans",
        headers=globex_headers,
        json={"engine": "dns_recon", "target": "app.acme.example.com"},
    )
    assert theirs.status_code == 403
    assert theirs.json()["error"]["details"]["reason"] == "not_in_scope"
    assert client.get(f"/api/v1/scans/{mine}", headers=acme_headers).json()["status"] == "pending"
