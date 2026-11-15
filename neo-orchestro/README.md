# Neo-Orchestro

**Automated Security Assessment & Orchestration Platform**
*Designed & Developed by Ronald TSR.*

Neo-Orchestro orchestrates security assessments behind a modern web UI, under a strict,
auditable rule: **nothing runs against a target that has not been explicitly authorised.**

> **Use only on systems you are authorised to test.** Scope is checked when a scan is
> requested *and again* when a worker is about to run it.

## What works today (v0.1.0)

| Area | Status |
|---|---|
| Authentication (Argon2id, short JWT, rotating refresh cookie, lockout), RBAC (viewer / analyst / admin), organisation isolation, append-only audit log | ✅ implemented, tested |
| Scope engine (domains, IPs, CIDR; internal/external; DNS validation + pinning; redirect guard) | ✅ implemented, tested |
| Async orchestrator (Celery + Redis): queue, cancel, resume after crash, partial results, hard deadline | ✅ implemented, tested |
| Engine framework (allowlist, safe subprocess runner, normalised findings) + first engine `dns_recon` | ✅ implemented, tested |
| Web UI: dashboard, scans, scope, users, audit log, settings | ✅ implemented, tested |
| Real-process end-to-end test (API + worker + nginx + fake DNS + Chromium) | ✅ [`e2e/`](e2e/README.md): 94 API + 22 browser checks green |
| Docker images + Compose stack, CI, backup scripts | ✅ built and run once; e2e green on the Docker stack · CI workflow not yet run |
| Nmap, Nuclei, OSINT, web/TLS checks, PDF/HTML/JSON reports | ⏳ roadmap (phases 3–6) |

> **Honest limits.** The images and the Compose stack were built and run once in the authoring
> sandbox and passed the e2e suites there (see [`docs/operations.md`](docs/operations.md#known-limitations)),
> which found and fixed two real defects (worker crash, stale nginx upstream). The GitHub Actions
> workflow has not run yet, and nothing was tested on Docker Desktop or behind production TLS.

## Quick start (Docker Compose)

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(48))"   # → NEO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # → POSTGRES_PASSWORD, REDIS_PASSWORD
$EDITOR .env        # fill NEO_SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD

make up             # build + start (db, redis, migrate, api, worker, web)
make create-org NAME="Acme" SLUG=acme EMAIL=admin@acme.example.com   # prompts for the password
```

Open <http://127.0.0.1:8080>. The web UI is the only published port and binds to loopback.

*Local evaluation over plain HTTP:* browsers do not send `Secure` cookies over HTTP (except on
`localhost` in some browsers), so for a quick local try set `NEO_ENV=development` and
`NEO_COOKIE_SECURE=false` in `.env`. Production keeps both defaults behind a TLS proxy.

First steps in the UI: **Périmètre → Ajouter une autorisation** (e.g. `acme.example.com` with
sub-domains), then **Scans → Nouveau scan** with the `dns_recon` engine.

## Development setup

```bash
# PostgreSQL 16 + Redis 7 on loopback
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d db redis   # or use local services

# backend
cd backend && make install                      # venv from hash-locked requirements
export NEO_SECRET_KEY=... NEO_DATABASE_URL=postgresql+pg8000://neo:...@localhost:5432/neo_orchestro \
       NEO_REDIS_URL=redis://:...@localhost:6379/0
.venv/bin/alembic upgrade head
.venv/bin/uvicorn neo_orchestro.api.app:create_app --factory --reload
.venv/bin/celery -A neo_orchestro.orchestrator.worker:app worker -Q scans --loglevel INFO
.venv/bin/python -m neo_orchestro.cli create-org --name Acme --slug acme --admin-email admin@acme.example.com --password-stdin

# frontend (proxies /api and /health to 127.0.0.1:8000)
cd frontend && npm ci && npm run dev            # http://127.0.0.1:5173
```

Quality gates (all must be green before committing): `make check` in `backend/` (Ruff,
mypy `--strict`, pytest on a real PostgreSQL and Redis) and `npm run check` in `frontend/`
(tsc, ESLint, Prettier, Vitest). See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Documentation

| Document | Content |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Components, trust boundaries, scan lifecycle, data model, how to add an engine |
| [`docs/adr/`](docs/adr/README.md) | Every design decision with the alternatives rejected |
| [`docs/operations.md`](docs/operations.md) | Deploy, upgrade, backup/restore, secrets, monitoring, hardening, known limitations |
| [`SECURITY.md`](SECURITY.md) | Threat model, controls, vulnerability reporting |
| [`docs/licences.md`](docs/licences.md) | Dependencies, justifications, licences |
| [`CLAUDE.md`](CLAUDE.md) | Working contract for contributors and coding agents |

## API at a glance

OpenAPI is served at `/docs` outside production. All business endpoints live under `/api/v1`.

| Endpoint | Role |
|---|---|
| `POST /auth/login` · `POST /auth/refresh` · `POST /auth/logout` · `GET /auth/me` · `POST /auth/change-password` | public / session |
| `GET /scope/entries` · `POST /scope/entries` · `DELETE /scope/entries/{id}` · `POST /scope/check` | viewer / admin / admin / analyst |
| `GET /engines` · `POST /scans` (202) · `GET /scans` · `GET /scans/{id}` · `GET /scans/{id}/findings` · `POST /scans/{id}/cancel` | viewer · analyst · viewer · viewer · viewer · analyst |
| `GET/POST/PATCH /users` · `GET /audit-logs` | admin |
| `GET /health/live` · `GET /health/ready` · `GET /metrics` | operational (unversioned) |

Errors share one envelope: `{"error": {"code", "message", "details", "request_id"}}`.

## Configuration

All settings are `NEO_*` environment variables ([`.env.example`](.env.example)); secrets are
never stored in Git. Production mode refuses insecure combinations (non-secure cookies,
`CHANGE_ME` placeholders).

| Variable | Default | Meaning |
|---|---|---|
| `NEO_SECRET_KEY` | — (required) | ≥ 32 chars; signs tokens |
| `NEO_DATABASE_URL` | — (required) | `postgresql+pg8000://…` |
| `NEO_REDIS_URL` | — (required) | Celery broker |
| `NEO_ENV` | `development` (Compose: `production`) | `development` \| `test` \| `production` |
| `NEO_COOKIE_SECURE` | `false` (Compose: `true`) | Must be `true` in production |
| `NEO_ACCESS_TOKEN_TTL_MINUTES` / `NEO_REFRESH_TOKEN_TTL_DAYS` | 15 / 7 | Token lifetimes |
| `NEO_LOGIN_MAX_FAILED_ATTEMPTS` / `NEO_LOGIN_LOCKOUT_MINUTES` | 5 / 15 | Account lockout |
| `NEO_SCOPE_MIN_PREFIX_V4` / `_V6` | 16 / 48 | Smallest CIDR an organisation may authorise |
| `NEO_SCAN_MAX_DURATION_SECONDS` | 900 | Hard scan deadline |
| `NEO_DNS_TIMEOUT_SECONDS` | 5 | DNS lookup lifetime |
| `NEO_DNS_NAMESERVERS` | empty (host resolver) | Comma-separated resolver IPs; use a trusted resolver |
| `NEO_CORS_ORIGINS` | empty (closed) | Explicit origins only; `*` is rejected |
| `NEO_LOG_LEVEL` / `NEO_LOG_JSON` / `NEO_METRICS_ENABLED` | INFO / false / true | Observability |

## Security model (summary)

- **Default-deny scope**, validated at request time and again at execution; hard-denied ranges
  (loopback, link-local, cloud metadata, multicast, reserved) can never be scanned.
- **No shell, ever.** Engines are an in-code allowlist; tools run with an argv list, a minimal
  environment, resource limits and a process-group kill.
- **Tenant isolation by construction** (org-scoped repositories; cross-tenant access is a 404).
- **Short-lived access token in memory, rotating HttpOnly refresh cookie with reuse detection.**
- **Append-only audit log**, enforced by database triggers; denials are audited too.
- Hash-locked dependencies, `pip-audit` / `npm audit`, non-root read-only containers.

Details and known limits: [`SECURITY.md`](SECURITY.md), ADRs 0004–0007.

## Roadmap

1. ✅ Foundations, authentication, database, RBAC, scope
2. ✅ Orchestrator and reconnaissance (`dns_recon`)
3. ⏳ Nmap adapter and asset inventory
4. ⏳ Nuclei adapter and vulnerability normalisation
5. ⏳ OSINT and web/TLS controls
6. ⏳ Reporting (PDF/HTML/JSON) and dashboards
7. ⏳ Security testing campaign, optimisation, publication

## Licence

Neo-Orchestro has **no licence chosen yet** (all rights reserved by its author). Third-party
components keep their own licences ([`docs/licences.md`](docs/licences.md)). The code is an
independent implementation and contains nothing from the Sn1per repository that hosts it
([ADR 0001](docs/adr/0001-independent-implementation.md)); move it to its own repository before
any public release.
