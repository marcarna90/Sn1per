# Security

Neo-Orchestro is security tooling: it must be both *safe to run* and *safe to be pointed at
targets*. This document states the threat model, the controls (with where they are tested) and how
to report a vulnerability.

## Reporting a vulnerability

> **TODO (owner):** publish a private contact (a security mailbox or the hosting platform's
> private vulnerability reporting) here before any public release. Until then there is no
> disclosure channel; do not open public issues for vulnerabilities.

Please include the version, steps to reproduce, impact, and the `request_id` if the API returned
one. Do not test against systems you do not own or have permission to test.

## Responsible use

The platform scans only targets an organisation administrator has authorised, and keeps an
append-only record of who authorised and who ran what. It is intended for audits you are entitled
to perform. Misuse is outside its purpose and unsupported.

## Threat model (summary)

| Threat | Main controls | Tests |
|---|---|---|
| Scanning outside the authorised perimeter / SSRF via the scanner | Default-deny scope; hard-denied ranges; strict target parsing; DNS validation + pinning; re-validation at execution; redirect guard | `tests/security/test_scope_engine.py`, `tests/integration/test_scan_runner.py` |
| Command / argument injection | Engine allowlist in code; argv-only subprocess (no shell); validated targets cannot start with `-`; only the scan id crosses the broker | `tests/unit/test_process.py`, `test_engines.py`, `test_scan_service.py` |
| Cross-tenant data access | Org-scoped repositories; 404 for foreign ids; tenant from the verified token only | `tests/security/test_api_authorisation.py` |
| Credential theft / session hijack | Argon2id; 15-min access token in memory; rotating HttpOnly SameSite=Strict refresh cookie with reuse detection; CSRF header; lockout; generic login errors | `tests/unit/test_security_primitives.py`, `tests/integration/test_auth_service.py`, `frontend/src/auth` |
| Privilege escalation | RBAC enforced in API **and** services; role re-read from the database on each request; last-admin protection | RBAC matrix, `test_user_service.py` |
| Tampering with the audit trail | Database triggers reject UPDATE/DELETE/TRUNCATE; denials audited | `tests/integration/test_migrations.py` |
| Poisoned message queue | JSON-only Celery; broker carries only an id | `tests/integration/test_celery.py` |
| Runaway or hostile tool | CPU/memory/file limits, process-group kill, bounded output, findings cap, hard deadline | `tests/unit/test_process.py`, runner tests |
| Information leakage | Uniform error envelope; validation errors never echo input; internal errors generic; log redaction | `test_api_system.py`, `test_logging.py` |
| Supply chain | Hash-locked installs; `pip-audit` / `npm audit`; licence gate; no install scripts in the web build; wheels only in the image | CI, ADR 0010 |
| XSS in the UI | React escaping; strict CSP (`default-src 'self'`); no token in web storage | ADR 0009 |

Safeguard tests are additionally *mutation-checked*: each guard was temporarily disabled to confirm
the suite fails (a test that cannot fail protects nothing).

## Not covered / open

See [`docs/operations.md#known-limitations`](docs/operations.md#known-limitations) and the "Known
limits" sections of ADR 0004, 0005, 0006 and 0007. In particular: no MFA, no per-IP rate limiting
in the app, no key rotation window, no public-suffix check, no stale-scan reaper, and the CI workflow
has not run yet (the images were built and run once in the authoring sandbox).

## Supported versions

Pre-release (0.x): only the latest commit is supported.
