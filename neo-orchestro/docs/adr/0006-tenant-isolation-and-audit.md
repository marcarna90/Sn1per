# ADR 0006 — Tenant isolation by construction, append-only audit

Status: Accepted

## Context

Governance requirements: separation of organisations, access control on results,
audit logs, and each scan records who/what/when/how. A cross-tenant data leak is
the most damaging bug class for a multi-organisation security platform.

## Decision

### Tenancy
- `organizations` is the tenant boundary. Every business row carries `org_id`
  (a NOT NULL foreign key). A user belongs to exactly one organisation
  (multi-org membership is deliberately deferred — YAGNI, no migration pain
  later since membership would be a new table).
- **Org-scoped repositories** (`repositories/`): constructed with the caller's
  `org_id`; every query includes it. There is no repository method that reads
  business data without an organisation, so "forgetting the filter" is not
  expressible in service or router code.
- Cross-tenant access answers **404**, never 403, so identifiers do not leak
  existence. Covered by `tests/security/test_tenant_isolation.py`.
- The organisation id comes from the verified access token, never from the
  request body or URL.
- Database foreign keys use `RESTRICT` for users → organisation (an organisation
  with users cannot be deleted by accident) and `CASCADE` for derived data
  (scans, findings, scope entries).
- No ORM relationships between aggregates: explicit, org-filtered queries only,
  so lazy loading can never cross a tenant boundary.

### Audit log
- `audit_logs` is **append-only, enforced in the database**: triggers reject
  `UPDATE`, `DELETE` (per row) and `TRUNCATE` (migration `0001`). Tested in
  `tests/integration/test_migrations.py`.
- No foreign keys: the trail must outlive the objects it describes.
- Records: actor, org, action (`auth.login`, `scope.create`, `scan.create`, …),
  resource, outcome (`success|denied|failure`), client IP, request id, details.
  Secrets are never written (details pass through the same redaction as logs).
- Both successes and **denials** are audited (failed logins, scope refusals).

## Limits (stated honestly)

A database *owner* can still `ALTER TABLE … DISABLE TRIGGER`. The trigger
protects against application bugs and a compromised application credential, not
against a compromised DBA. Production must run the app with a role that does
not own the tables (migrations use a separate role); hash-chaining or shipping
the audit stream to external WORM storage are future hardening options.

## Alternatives rejected

- *PostgreSQL row-level security* — strong, but couples correctness to session
  GUCs set on every connection/worker; repository scoping plus tests is simpler
  to reason about now. Can be layered on later as defence in depth.
- *Schema-per-tenant / database-per-tenant* — operational overhead without need.
- *Soft-delete of audit rows* — still a mutation; refused.
