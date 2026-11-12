# Architecture Decision Records

One short file per significant decision. Status: Proposed → **Accepted** → Superseded.
Template: Context / Decision / Alternatives rejected / Consequences.

| ADR | Decision | Status |
|-----|----------|--------|
| [0001](0001-independent-implementation.md) | Independent implementation, isolated tree (Sn1per licence) | Accepted |
| [0002](0002-modular-monolith-layering.md) | Modular monolith with strict layering and ports/adapters | Accepted |
| [0003](0003-sync-sqlalchemy-pg8000.md) | Synchronous SQLAlchemy 2 with the `pg8000` driver | Accepted |
| [0004](0004-scope-engine.md) | Scope engine: allowlist, hard-denied ranges, DNS pinning, re-validation | Planned |
| [0005](0005-authentication.md) | Argon2id, short JWT access token, rotating refresh cookie | Planned |
| [0006](0006-tenant-isolation-and-audit.md) | Org-scoped repositories, append-only audit log | Accepted |
| [0007](0007-orchestration.md) | Celery/Redis orchestration, engine allowlist, safe subprocess | Planned |
| [0008](0008-normalised-findings.md) | Common normalised findings schema | Accepted |
| [0009](0009-frontend.md) | Frontend stack and token handling | Planned |
| [0010](0010-dependencies-and-licences.md) | Dependency management and licence policy | Accepted |
