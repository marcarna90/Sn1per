# ADR 0002 — Modular monolith with strict layering

Status: Accepted

## Context

Requirements: modular, maintainable, extensible; frontend / API / workers /
scan engines / business services / persistence kept separate; all scans through
an asynchronous orchestrator. A small team, one deployable domain.

## Decision

One Python package (`neo_orchestro`), several **deployable processes** from the
same image: `api` (FastAPI/uvicorn) and `worker` (Celery). Inside the package:

```
api ─► services ─► repositories ─► db (models)
          │
          ├─► scope        (pure; resolver injected)
          └─► orchestrator ─► engines (ports/adapters)
core  (config, logging, errors, crypto primitives) — imported by all, imports none
```

Rules (enforced by review and by an import-direction test,
`tests/unit/test_architecture.py`):

- `core/` and `scope/` import nothing from `api`, `services`, `repositories`,
  `orchestrator` or `db`.
- `api/` routers are thin: parse → call a service → serialise.
- Scan engines implement an `Engine` protocol; the orchestrator knows only the
  protocol and an explicit registry (allowlist).
- External effects (DNS, subprocess, clock, Redis) are injected, so core logic
  is unit-testable without mocks of internals.

## Alternatives rejected

- *Microservices* — operational cost with no present benefit; the split
  api/worker already gives process isolation where it matters (scanners).
- *Flat package / "fat routers"* — the pattern that makes injection and
  tenancy bugs likely.

## Consequences

- Extracting a service later (e.g. a dedicated scanner fleet) is mechanical:
  the worker already depends only on services and the DB.
- Slight boilerplate (repository + service per aggregate) accepted for safety.
