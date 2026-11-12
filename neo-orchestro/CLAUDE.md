# CLAUDE.md — Neo-Orchestro

Automated Security Assessment & Orchestration Platform.
Designed & Developed by Ronald TSR. Linux. Authorised audits only.

This file is the working contract for any agent or developer on this project.
Decisions live in `docs/adr/`; read the relevant ADR before changing a design.

## Hard rules (security first)

1. **No scan runs without a scope decision.** Every execution path calls
   `ScopeEngine.evaluate()` and runs against the *pinned* IPs it returns.
   Scope is re-checked in the worker at execution time (not only at the API).
2. **Never build a shell command from user input.** `subprocess` is always
   called with an argv list, `shell=False`, via `engines/process.py`. Engines
   are an explicit allowlist (`orchestrator/engines/registry.py`).
3. **Tenant isolation by construction.** Data access goes through
   org-scoped repositories (`repositories/`); a query without an `org_id`
   must not be expressible. Cross-tenant access returns 404, not 403.
4. **Secrets never enter Git.** Config comes from `NEO_*` env vars
   (`.env` is ignored; `.env.example` holds placeholders only).
5. **Audit everything security-relevant** (auth, scope decisions, scan
   lifecycle, admin actions). The audit table is append-only (DB trigger).
6. **Never claim success without evidence.** Report real command output;
   say plainly what was not run (e.g. Docker daemon unavailable).
7. **No Sn1per code.** This project is an independent implementation
   (ADR 0001). Do not copy templates, scripts or wordlists from the parent
   repository.

## Layout

```
backend/src/neo_orchestro/
  core/          config, logging, errors, security primitives (no I/O to DB)
  db/            engine/session, SQLAlchemy models
  scope/         pure scope engine (no DB, no network except injected resolver)
  engines/       engine port, allowlist registry, safe process runner, adapters
  repositories/  org-scoped data access (+ one internal worker repository)
  services/      business logic (auth, users, scope, scans, audit); owns transactions
  api/           FastAPI app: deps, v1 routers, schemas (thin)
  orchestrator/  Celery app, scan runner, dispatcher, worker entry point
frontend/        React + TypeScript + Tailwind (Vite)
docs/            architecture + ADRs
```

Dependency direction: `api → services → repositories → db`;
`services → scope, engines`; `orchestrator → services, repositories, scope, engines`.
`core/`, `scope/` and `engines/` import nothing from the layers above them; `services/`
never imports `orchestrator/` (the queue is a port). Enforced by
`tests/unit/test_architecture.py`. Routers contain no business logic.

## Commands

```bash
# backend (from backend/)
make install     # venv from the hash-locked requirements
make check       # ruff format --check + ruff check + mypy --strict + pytest (must be green)
make test        # pytest (needs PostgreSQL + Redis, see .env.example / NEO_TEST_DATABASE_URL)
make lock        # regenerate requirements*.txt from pyproject.toml (review the diff)
make audit       # pip-audit on the runtime lock
python -m neo_orchestro.cli create-org ...   # bootstrap an organisation (password via stdin/prompt)

# frontend (from frontend/)
npm run check    # tsc + eslint + prettier --check + vitest
npm run build

# stack (from the project root)
make up / down / logs / create-org / backup
```

## Conventions

- Python 3.12+, fully typed (`mypy --strict`), Ruff-formatted, Google-style
  docstrings on public API. Pydantic v2 for all I/O schemas.
- Tests: `tests/unit` (pure), `tests/integration` (real Postgres/Redis),
  `tests/security` (threat-table driven). Write the failing test first for
  security-relevant code.
- Commits: Conventional Commits (`feat|fix|docs|test|refactor|security|chore`).
  Branches `feature/*`, `fix/*`, `docs/*` off `develop`; `main` is releases.
  **Never push without an explicit request.**
- New dependency ⇒ one-line justification + licence check in
  `docs/licences.md`. Copyleft (GPL/AGPL) libraries are not imported;
  GPL tools may only be executed as separate processes.
- UI/reports carry the signature "Designed & Developed by Ronald TSR".

## Definition of done

Typed, documented, tested (unit + relevant integration/security), `make check`
green, ADR/docs/CHANGELOG updated, files touched + tests run + known limits
summarised.
