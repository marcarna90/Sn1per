# Dependencies, justification and licences

Policy: [ADR 0010](adr/0010-dependencies-and-licences.md). Verified 2026-11-12
against the committed lock files (`pip-audit`: no known vulnerabilities).
Neo-Orchestro itself has no licence chosen yet (all rights reserved).

## Backend — direct runtime dependencies

| Package | Version | Licence | Why it is needed |
|---|---|---|---|
| fastapi | 0.162.5 | MIT | HTTP API framework (required stack) |
| uvicorn | 0.54.0 | BSD-3-Clause | ASGI server |
| pydantic / pydantic-settings | 2.14.3 / 2.16.2 | MIT | Typed schemas and env-based configuration |
| email-validator | 2.3.0 | Unlicense | Strict e-mail validation (`EmailStr`) |
| sqlalchemy | 2.1.8 | MIT | ORM (required stack) |
| pg8000 | 1.31.6 | BSD | Pure-Python PostgreSQL driver, no copyleft (ADR 0003) |
| alembic | 1.20.1 | MIT | Schema migrations (required stack) |
| celery / redis | 5.7.0 / 8.1.0 | BSD-3 / MIT | Asynchronous orchestrator + broker client (required stack) |
| argon2-cffi | 25.1.0 | MIT | Argon2id password hashing (ADR 0005) |
| pyjwt | 2.15.1 | MIT | Signed access/refresh tokens |
| dnspython | 2.9.2 | ISC | DNS resolution with timeouts for scope pinning and recon |
| structlog | 26.1.0 | MIT OR Apache-2.0 | Structured logs (observability requirement) |
| prometheus-client | 0.26.0 | Apache-2.0 AND BSD-2 | Metrics endpoint (observability requirement) |

Dev only: pytest, pytest-cov, httpx (test client), ruff, mypy, pip-tools,
pip-audit — all MIT/BSD/Apache.

Transitive tree: 46 packages in total, none under GPL/AGPL/SSPL
(`requirements.txt` is the source of truth).

## Explicitly avoided

| Candidate | Licence | Decision |
|---|---|---|
| python-nmap | GPL-3.0 | Not imported. Nmap is run as a subprocess; XML parsed by us. |
| psycopg | LGPL-3.0 | Not used; see ADR 0003. |

## Frontend

Added with the frontend step (see ADR 0009).
