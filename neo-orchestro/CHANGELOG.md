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
