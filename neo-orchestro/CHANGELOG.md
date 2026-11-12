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
