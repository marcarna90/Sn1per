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
| packaging (via `celery[redis]`) | 26.3 | Apache-2.0 OR BSD-2 | Imported by kombu's Redis transport but declared only in its `redis` extra; without it the worker image crashes at start-up (found by the first real image run) |
| argon2-cffi | 25.1.0 | MIT | Argon2id password hashing (ADR 0005) |
| pyjwt | 2.15.1 | MIT | Signed access/refresh tokens |
| dnspython | 2.9.2 | ISC | DNS resolution with timeouts for scope pinning and recon |
| structlog | 26.1.0 | MIT OR Apache-2.0 | Structured logs (observability requirement) |
| prometheus-client | 0.26.0 | Apache-2.0 AND BSD-2 | Metrics endpoint (observability requirement) |

Dev only: pytest, pytest-cov, httpx2 (test client; Starlette's TestClient requires it, BSD-3),
ruff, mypy, pip-tools, pip-audit — all MIT/BSD/Apache.

Transitive tree: 46 packages in total, none under GPL/AGPL/SSPL
(`requirements.txt` is the source of truth).

## Explicitly avoided

| Candidate | Licence | Decision |
|---|---|---|
| python-nmap | GPL-3.0 | Not imported. Nmap is run as a subprocess; XML parsed by us. |
| psycopg | LGPL-3.0 | Not used; see ADR 0003. |

## Frontend

Policy and rationale: [ADR 0009](adr/0009-frontend.md). Generated from the installed
`node_modules` (verified 2026-11-12; `npm audit`: 0 vulnerabilities).

| Package | Version | Licence | Used |
|---|---|---|---|
| @tanstack/react-query | 5.107.1 | MIT | runtime (bundled) |
| react | 19.3.1 | MIT | runtime (bundled) |
| react-dom | 19.3.1 | MIT | runtime (bundled) |
| react-router-dom | 7.18.5 | MIT | runtime (bundled) |
| @eslint/js | 10.0.1 | MIT | build / test / lint only |
| @tailwindcss/vite | 4.3.5 | MIT | build / test / lint only |
| @testing-library/jest-dom | 7.0.1 | MIT | build / test / lint only |
| @testing-library/react | 16.3.3 | MIT | build / test / lint only |
| @testing-library/user-event | 14.6.10 | MIT | build / test / lint only |
| @types/node | 22.20.5 | MIT | build / test / lint only |
| @types/react | 19.3.0 | MIT | build / test / lint only |
| @types/react-dom | 19.3.0 | MIT | build / test / lint only |
| @vitejs/plugin-react | 6.3.0 | MIT | build / test / lint only |
| eslint | 10.14.0 | MIT | build / test / lint only |
| eslint-plugin-react-hooks | 7.1.1 | MIT | build / test / lint only |
| globals | 17.14.0 | MIT | build / test / lint only |
| jest-axe | 11.0.0 | MIT | build / test / lint only |
| jsdom | 31.0.0 | MIT | build / test / lint only |
| prettier | 3.10.1 | MIT | build / test / lint only |
| tailwindcss | 4.3.5 | MIT | build / test / lint only |
| typescript | 6.0.3 | Apache-2.0 | build / test / lint only |
| typescript-eslint | 8.72.2 | MIT | build / test / lint only |
| vite | 8.3.8 | MIT | build / test / lint only |
| vitest | 5.1.0 | MIT | build / test / lint only |

Transitive tree (`npm ls --all`): MIT 150, ISC 7, Apache-2.0 4, BSD 3, plus build/test-time
**MPL-2.0** (`axe-core`, `lightningcss` — not bundled, not modified) and **CC-BY-4.0** data
(`caniuse-lite`, build-time). No GPL/AGPL. 21 further entries are platform-specific optional
binaries of the build tools.
