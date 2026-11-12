"""Scan endpoints: engines, create (202), list, read, findings, cancel."""

import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from neo_orchestro.api.deps import get_dispatcher
from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import ScopeKind
from neo_orchestro.engines import EngineRegistry
from neo_orchestro.orchestrator.runner import WorkerDeps, execute_scan
from neo_orchestro.scope import StaticResolver
from neo_orchestro.services.scans import DispatchError
from neo_orchestro.services.scope import ScopeService
from support import PASSWORD, InMemoryDispatcher, SharedSession, Tenant, bearer, principal_of

MakeTenant = Callable[..., Tenant]
Login = Callable[[str, str], str]
SCANS = "/api/v1/scans"


@pytest.fixture
def analyst_headers(
    db_session: Session, settings: Settings, make_tenant: MakeTenant, login: Login
) -> dict[str, str]:
    tenant = make_tenant()
    ScopeService(db_session, principal_of(tenant.admin), settings).add_entry(
        ScopeKind.domain, "acme.example.com", include_subdomains=True
    )
    return bearer(login(tenant.admin.email, PASSWORD))


def create(client: TestClient, headers: dict[str, str], **body: Any) -> Any:
    payload = {"engine": "dns_recon", "target": "app.acme.example.com", **body}
    return client.post(SCANS, headers=headers, json=payload)


# ------------------------------------------------------------------ engines


@pytest.mark.integration
def test_engines_are_listed(client: TestClient, analyst_headers: dict[str, str]) -> None:
    [engine] = client.get("/api/v1/engines", headers=analyst_headers).json()
    assert engine["name"] == "dns_recon"
    assert engine["target_kinds"] == ["domain"]
    assert engine["description"]


# ------------------------------------------------------------------ create


@pytest.mark.integration
def test_creating_a_scan_returns_202_and_queues_it(
    client: TestClient, analyst_headers: dict[str, str], dispatcher: InMemoryDispatcher
) -> None:
    response = create(client, analyst_headers, params={"record_types": ["a"]})
    assert response.status_code == 202
    scan = response.json()
    assert response.headers["location"] == f"{SCANS}/{scan['id']}"
    assert scan["status"] == "pending"
    assert scan["engine"] == "dns_recon"
    assert scan["params"] == {"record_types": ["A"]}
    assert scan["scope_decision"]["allowed"] is True
    assert scan["started_at"] is None
    assert dispatcher.ids == [uuid.UUID(scan["id"])]


@pytest.mark.integration
@pytest.mark.security
def test_out_of_scope_targets_are_forbidden_with_a_reason_and_nothing_is_queued(
    client: TestClient, analyst_headers: dict[str, str], dispatcher: InMemoryDispatcher
) -> None:
    for target, reason in [
        ("evil.net", "not_in_scope"),
        ("evil.acme.example.com", "blocked_address"),
        ("http://app.acme.example.com", "invalid_target"),
        ("127.0.0.1", "blocked_address"),
    ]:
        response = create(client, analyst_headers, target=target)
        assert response.status_code == 403, target
        error = response.json()["error"]
        assert error["code"] == "scope_violation"
        assert error["details"]["reason"] == reason
    assert dispatcher.ids == []
    assert client.get(SCANS, headers=analyst_headers).json() == []


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    "engine_name", ["nmap", "dns_recon; rm -rf /", "../../bin/sh", "", "x" * 100]
)
def test_unknown_engines_are_unprocessable(
    client: TestClient,
    analyst_headers: dict[str, str],
    dispatcher: InMemoryDispatcher,
    engine_name: str,
) -> None:
    assert create(client, analyst_headers, engine=engine_name).status_code == 422
    assert dispatcher.ids == []


@pytest.mark.integration
@pytest.mark.security
@pytest.mark.parametrize(
    "extra",
    [
        {"status": "succeeded"},
        {"org_id": str(uuid.uuid4())},
        {"requested_by_id": str(uuid.uuid4())},
        {"scope_decision": {"allowed": True}},
        {"celery_task_id": "x"},
    ],
)
def test_server_controlled_fields_cannot_be_set_by_the_client(
    client: TestClient, analyst_headers: dict[str, str], extra: dict[str, Any]
) -> None:
    assert create(client, analyst_headers, **extra).status_code == 422


@pytest.mark.integration
@pytest.mark.parametrize(
    "params", [{"record_types": ["AXFR"]}, {"nameserver": "8.8.8.8"}, {"record_types": "A"}]
)
def test_invalid_params_are_unprocessable(
    client: TestClient, analyst_headers: dict[str, str], params: dict[str, Any]
) -> None:
    response = create(client, analyst_headers, params=params)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"


@pytest.mark.integration
def test_oversized_params_are_rejected(client: TestClient, analyst_headers: dict[str, str]) -> None:
    assert create(client, analyst_headers, params={"k": "x" * 20_000}).status_code == 422


@pytest.mark.integration
def test_a_broken_queue_returns_503_and_marks_the_scan_failed(
    app: Any, client: TestClient, analyst_headers: dict[str, str]
) -> None:
    class Broken:
        def enqueue(self, scan_id: uuid.UUID) -> str:
            raise DispatchError("broker down")

    app.dependency_overrides[get_dispatcher] = Broken
    response = create(client, analyst_headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_unavailable"
    [scan] = client.get(SCANS, headers=analyst_headers).json()
    assert (scan["status"], scan["error_code"]) == ("failed", "dispatch_failed")


# ------------------------------------------------------------------ read


@pytest.mark.integration
def test_list_filter_paginate_and_get(client: TestClient, analyst_headers: dict[str, str]) -> None:
    ids = [create(client, analyst_headers).json()["id"] for _ in range(3)]
    listing = client.get(SCANS, headers=analyst_headers).json()
    assert [s["id"] for s in listing] == list(reversed(ids))  # newest first

    assert client.get(SCANS, headers=analyst_headers, params={"status": "succeeded"}).json() == []
    assert len(client.get(SCANS, headers=analyst_headers, params={"status": "pending"}).json()) == 3
    page = client.get(SCANS, headers=analyst_headers, params={"limit": 1, "offset": 1}).json()
    assert [s["id"] for s in page] == [ids[1]]
    for bad in ({"status": "exploded"}, {"limit": 0}, {"limit": 500}, {"offset": -1}):
        assert client.get(SCANS, headers=analyst_headers, params=bad).status_code == 422

    assert client.get(f"{SCANS}/{ids[0]}", headers=analyst_headers).json()["id"] == ids[0]
    assert client.get(f"{SCANS}/{uuid.uuid4()}", headers=analyst_headers).status_code == 404
    assert client.get(f"{SCANS}/not-a-uuid", headers=analyst_headers).status_code == 422


@pytest.mark.integration
def test_findings_after_the_worker_has_run(
    client: TestClient,
    db_session: Session,
    settings: Settings,
    clock: Any,
    api_registry: EngineRegistry,
    analyst_headers: dict[str, str],
) -> None:
    scan_id = create(client, analyst_headers).json()["id"]
    deps = WorkerDeps(
        session_factory=lambda: SharedSession(db_session),
        registry=api_registry,
        resolver=StaticResolver({"app.acme.example.com": ["93.184.216.34"]}),
        settings=settings,
        clock=clock,
        poll_interval=0.0,
    )
    assert execute_scan(deps, uuid.UUID(scan_id)) is not None

    scan = client.get(f"{SCANS}/{scan_id}", headers=analyst_headers).json()
    assert scan["status"] == "succeeded"
    assert scan["started_at"]
    assert scan["finished_at"]
    assert scan["attempts"] == 1

    findings = client.get(f"{SCANS}/{scan_id}/findings", headers=analyst_headers).json()
    assert {f["title"] for f in findings} == {"A record", "TXT record"}
    one = findings[0]
    assert set(one) == {
        "id", "scan_id", "category", "severity", "title", "asset",
        "description", "evidence", "source_engine", "created_at",
    }  # fmt: skip
    assert one["scan_id"] == scan_id
    assert one["source_engine"] == "dns_recon"

    info = client.get(
        f"{SCANS}/{scan_id}/findings", headers=analyst_headers, params={"severity": "info"}
    )
    assert len(info.json()) == 2
    high = client.get(
        f"{SCANS}/{scan_id}/findings", headers=analyst_headers, params={"severity": "high"}
    )
    assert high.json() == []
    assert (
        client.get(
            f"{SCANS}/{scan_id}/findings", headers=analyst_headers, params={"severity": "bad"}
        ).status_code
        == 422
    )


# ------------------------------------------------------------------ cancel


@pytest.mark.integration
def test_cancel(client: TestClient, analyst_headers: dict[str, str]) -> None:
    scan_id = create(client, analyst_headers).json()["id"]
    cancelled = client.post(f"{SCANS}/{scan_id}/cancel", headers=analyst_headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["finished_at"] is not None
    assert client.post(f"{SCANS}/{scan_id}/cancel", headers=analyst_headers).status_code == 409
    assert client.post(f"{SCANS}/{uuid.uuid4()}/cancel", headers=analyst_headers).status_code == 404


@pytest.mark.integration
def test_the_audit_trail_tells_the_story_of_a_scan(
    client: TestClient, analyst_headers: dict[str, str]
) -> None:
    scan_id = create(client, analyst_headers).json()["id"]
    client.post(f"{SCANS}/{scan_id}/cancel", headers=analyst_headers)
    create(client, analyst_headers, target="evil.net")
    events = client.get("/api/v1/audit-logs", headers=analyst_headers, params={"limit": 200}).json()
    story = [
        (e["action"], e["outcome"]) for e in reversed(events) if e["action"].startswith("scan.")
    ]
    assert story == [
        ("scan.create", "success"),
        ("scan.cancel", "success"),
        ("scan.create", "denied"),
    ]
