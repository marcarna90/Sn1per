# Changelog

All notable changes to Neo-Orchestro. Format: Keep a Changelog; versioning: SemVer.

## [Unreleased]

### Added
- Project foundations: isolated `neo-orchestro/` tree, `CLAUDE.md`, ADRs 0001–0003,
  backend tooling (`pyproject.toml`), hash-pinned lockfiles.
- Core: typed settings (secure-by-default, production guards), structured logging with
  secret redaction, error hierarchy.
- Persistence: SQLAlchemy 2 models (organisations, users, refresh tokens, scope entries,
  scans, normalised findings, audit log) with database-level constraints; Alembic
  migration `0001`; append-only audit trail enforced by triggers; integration tests on
  real PostgreSQL (ADR 0003, 0006, 0008).
- Scope engine (`neo_orchestro.scope`): default-deny evaluation, strict target parsing,
  hard-denied address classes (loopback, link-local, metadata, multicast, reserved) incl. mapped/6to4/NAT64
  forms, DNS answer validation with pinning, redirect guard, validated rule creation, dnspython resolver
  adapter. 192 unit/security tests; mutation-checked (ADR 0004).
- Authentication and governance (ADR 0005, 0006): Argon2id passwords with policy, JWT access
  tokens (HS256 pinned, separate audiences), rotating HttpOnly refresh cookie with reuse
  detection, account lockout, CSRF header, per-request revalidation of role/activity/organisation.
- API v1 (FastAPI): auth, users, scope (incl. dry-run check), audit log, meta; `/health/live`,
  `/health/ready`, `/metrics`. Uniform error envelope (never echoes submitted values), request
  ids, security headers, closed-by-default CORS, docs off in production.
- Tenant-scoped repositories, org-isolated services, RBAC enforced in both API and services,
  append-only audit of successes **and** denials, bootstrap CLI (`neo-orchestro create-org`).
- 382 tests (unit, integration on real PostgreSQL/Redis, security); mutation-checked guards.
- Orchestration (ADR 0007): scan requests are checked against scope, queued (id only) on
  Celery/Redis and executed by a worker whose runner claims atomically, **re-validates scope at
  execution**, honours cancellation and a hard deadline, keeps partial results, de-duplicates
  findings and never leaks internal errors. Hardened Celery (JSON only, acks_late, no result
  backend).
- Engine framework (`neo_orchestro.engines`): allowlist registry, safe subprocess runner (no shell,
  minimal env, process-group kill, resource limits, bounded output), normalised findings, first
  engine `dns_recon` (DNS records + missing-SPF check).
- API: `/engines`, `/scans` (202 + Location), `/scans/{id}`, `/scans/{id}/findings`, `/scans/{id}/cancel`.
- 520 tests; 14/14 orchestration mutations and 6/6 subprocess-runner mutations detected.
- Frontend (ADR 0009): React 19 + TypeScript (strict) + Vite + Tailwind + TanStack Query. Dashboard,
  scans (create / follow / cancel / findings), scope (add / delete-with-confirmation / dry-run),
  users, audit log (filter + pagination) and settings (change password). Access token in memory
  only, HttpOnly refresh cookie, CSRF header, single-flight refresh, role-gated routes, explicit
  loading/error/empty/permission states, WCAG-oriented markup, French UI.
- 75 frontend tests (client, auth, every screen, axe); 14/14 UI-safeguard mutations detected;
  `npm audit`: 0 vulnerabilities.
- Delivery: backend and web Dockerfiles (hash-locked wheels only, non-root, no pip in the image,
  nginx-unprivileged with strict CSP and auth rate limiting), `docker-compose.yml` (internal
  network, only `web` published on loopback, read-only containers, capabilities dropped, required
  secrets), dev overlay, backup/restore scripts, GitHub Actions CI (backend matrix 3.12/3.13 on
  real PostgreSQL/Redis, frontend, images, secrets scan), Dependabot.
- Documentation: README, architecture (diagrams), operations guide, SECURITY, CONTRIBUTING.
- End-to-end smoke test (`e2e/`, `make e2e`): real uvicorn + Celery worker + nginx (the shipped
  `default.conf`) + PostgreSQL + Redis + a fake DNS server, driven over HTTP (94 checks) and with
  Chromium/Playwright (22 checks) — including DNS rebinding while a scan is queued, reuse
  detection of refresh tokens, tenant isolation, the append-only audit triggers and the nginx
  rate limiter. Not run in CI yet.

### Fixed
- Worker image crashed at start-up (`No module named 'packaging'`): kombu's Redis transport imports
  `packaging` but declares it only in its `redis` extra, and the project depended on `celery` and
  `redis` separately. Now `celery[redis]` (one new hashed pin, `packaging` 26.3). Dev tools had hidden it
  locally. Test `test_runtime_lock.py` checks the lock covers the extras the code relies on.
- Web container returned 502 after the API container was recreated: nginx resolved `api` once at
  start-up and kept the old IP. `default.conf` now resolves per request (`resolver 127.0.0.11` +
  variable in `proxy_pass`); test `test_deployment_config.py`; proven with a forced IP change.
- Web UI: a scan that finished while its findings were being polled could show « Terminé » next to
  « Aucun résultat pour le moment » until a manual reload, because findings polling stopped without
  a final refresh. `useScan` now refreshes the findings once when the scan leaves pending/running
  (regression test added; found by the browser e2e run).
- Web UI: the API client now drains the empty body of `204` responses; Chromium reported the logout
  request as `net::ERR_ABORTED` otherwise (the server had processed it).

### Verification (authoring environment, 2026-11-12)
Backend: ruff format/check, mypy `--strict`, 531 tests, 96 % coverage (real PostgreSQL 16 + Redis 7);
frontend: tsc, ESLint, Prettier, 75 tests, `npm audit` 0 vulnerabilities; `pip-audit` clean on both
lock files; Alembic upgrade → downgrade → upgrade on a fresh database; e2e 94 + 22 checks green.
- CI `images` job now starts the stack (`up --wait`, production mode), probes readiness through nginx
  and recreates the API. (Steps replayed locally; the workflow itself has not run on GitHub.)
- Docker verification (2026-11-15, authoring sandbox): images built (backend 294 MB, web 91 MB), all
  six services healthy, api/worker non-root + read-only + no capabilities, no pip in the image,
  e2e 94 + 22 checks green against the containers.
