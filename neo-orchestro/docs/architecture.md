# Architecture

Decisions and their alternatives are in [`adr/`](adr/README.md); this page shows how the pieces
fit together.

## Components

```mermaid
flowchart LR
  user([Browser]) -->|HTTPS| tls[TLS reverse proxy<br/>HSTS, WAF/rate limits]
  tls --> web[web: nginx<br/>static UI + CSP<br/>proxies /api, /health]
  web -->|/api, /health| api[api: FastAPI]
  api --> pg[(PostgreSQL)]
  api -->|scan id only| redis[(Redis broker)]
  redis --> worker[worker: Celery]
  worker --> pg
  worker -->|argv, no shell,<br/>pinned IPs| engines[[engines:<br/>dns_recon, later nmap / nuclei]]
  engines -.->|network I/O| targets([Authorised targets])
```

One Python package (`neo_orchestro`), two processes from the same image (`api`, `worker`).

```
api ─► services ─► repositories ─► db (models)
          ├─► scope      pure policy; DNS resolver injected
          └─► engines    ports + adapters + safe process runner
orchestrator (Celery app, runner, worker entry point) ─► services, repositories, scope, engines
core         config, logging, errors, crypto primitives — imports nothing above it
```

Enforced by `backend/tests/unit/test_architecture.py`. Routers only parse → call a service →
serialise. Services own transactions (each use case commits itself) so audit rows of *denied*
actions survive the error that follows.

## Trust boundaries

| Boundary | Control |
|---|---|
| Internet → web | TLS proxy; nginx CSP, rate limit on `/api/v1/auth/` |
| Browser → API | Bearer access token (memory only) + HttpOnly SameSite=Strict refresh cookie + CSRF header |
| API → PostgreSQL | Org-scoped repositories; DB constraints; append-only audit triggers |
| API → Redis → worker | JSON only; **only the scan id** crosses the broker; target/params are read from PostgreSQL |
| Worker → tools | In-code engine allowlist; argv list, minimal env, limits, process-group kill |
| Worker → targets | Scope re-validated at execution; engines receive **pinned** IPs |

## Scan lifecycle

```mermaid
sequenceDiagram
  participant U as Analyst (UI)
  participant A as API
  participant S as Scope engine
  participant D as PostgreSQL
  participant Q as Redis
  participant W as Worker
  participant E as Engine
  U->>A: POST /scans {engine, target, params}
  A->>A: engine on allowlist? params valid? (else 422)
  A->>S: evaluate(target) (DNS only for authorised names)
  S-->>A: Decision (allowed + pinned IPs) or denial (403 + reason)
  A->>D: INSERT scan(pending, scope_decision) + audit(scan.create)
  A->>Q: enqueue(scan id)
  A-->>U: 202 + Location
  Q->>W: deliver scan id (at-least-once)
  W->>D: atomic claim: pending|running → running (attempts+1)
  W->>S: re-evaluate(target) with fresh DNS and current rules
  alt denied now
    W->>D: failed(scope_denied) + audit(denied)
  else allowed
    W->>E: run(ctx{pinned IPs, deadline, cancel poll})
    E-->>W: normalised findings (streamed)
    W->>D: findings in batches (deduplicated by fingerprint)
    W->>D: succeeded | cancelled | failed(code) + audit(scan.finish)
  end
```

**State machine:** `pending → running → succeeded | failed | cancelled`.
A queued scan is cancelled by a conditional SQL transition; a running one gets
`cancel_requested_at` and stops at its next `ctx.check()`. After a worker crash the broker
redelivers; the claim re-enters `running` (up to 3 attempts) and de-duplication makes the rerun
idempotent.

## Data model

```mermaid
erDiagram
  organizations ||--o{ users : "has (RESTRICT)"
  organizations ||--o{ scope_entries : authorises
  organizations ||--o{ scans : owns
  organizations ||--o{ findings : owns
  users ||--o{ refresh_tokens : holds
  users ||--o{ scans : "requested_by (SET NULL)"
  scans ||--o{ findings : "produces (CASCADE)"
  audit_logs {
    bigint id PK
    uuid org_id "no FK: outlives its subject"
    text action
    text outcome
    jsonb details
  }
```

`audit_logs` rejects `UPDATE`, `DELETE` and `TRUNCATE` (trigger, migration `0001`).
`findings` are unique per `(scan_id, fingerprint)`; the fingerprint hashes
`[category, asset, title, key]` (ADR 0008).

## Error model and observability

- One error envelope with a stable `code` and the request id; validation errors never echo
  submitted values; unexpected errors are logged with a traceback but returned generically.
- Structured logs (structlog; JSON in Compose) with `request_id`; sensitive keys are redacted.
- `/health/live`, `/health/ready` (database + Redis), `/metrics`
  (`neo_http_requests_total{method,route,status}` with route *templates*, never raw paths).

## Adding an engine

1. Implement `Engine` (`engines/base.py`): `name`, `description`, `target_kinds`,
   `validate_params`, `run(ctx)` yielding `NormalisedFinding`. Call `ctx.check()` often.
2. External tool? Use `run_command(argv, …)` only; pass `ctx.pinned_ips`, not the host name, if
   the tool connects to the target. Map its native severities to the five-level scale.
3. Register it in `default_registry` (`engines/registry.py`) — deliberately, in code.
4. Tests: unit (parameters, mapping, cancellation), an injection/threat table, and an
   integration test through the runner. Check the licence (GPL tools are executed, never imported)
   and record it in `docs/licences.md`; write an ADR if the engine needs new capabilities.
