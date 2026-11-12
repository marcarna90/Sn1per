# Contributing

Read [`CLAUDE.md`](CLAUDE.md) (rules and layout) and the [ADRs](docs/adr/README.md) first.

## Workflow

- Branches: `main` (releases) ← `develop` ← `feature/*`, `fix/*`, `docs/*`.
- **Conventional Commits**: `feat`, `fix`, `docs`, `test`, `refactor`, `security`, `chore`.
- Small, coherent changes. Update docs, `CHANGELOG.md` and the relevant ADR in the same change.
- Never push to a shared remote without an explicit decision to do so.

## Before every commit

```bash
make -C backend check          # ruff format --check, ruff check, mypy --strict, pytest
cd frontend && npm run check   # tsc, eslint, prettier --check, vitest
```

Backend integration tests need PostgreSQL and Redis (see `.env.example`,
`NEO_TEST_DATABASE_URL`). `NEO_REQUIRE_SERVICES=1` turns an unreachable service into a failure
instead of a skip (CI sets it).

## Standards

- **Tests first** for anything security-relevant (scope, auth, isolation, execution). Write the
  failing test, watch it fail for the right reason, then implement. For a new guard, disable it
  once and confirm a test fails.
- Fully typed (`mypy --strict`, TypeScript `strict`), documented public API, no `print`/`console`.
- **No shell construction from input**, no engine outside the registry, no query without an
  `org_id`, no secret in Git, no inline `# noqa`/`type: ignore` without a reason.
- Dependencies: justify each in `docs/licences.md`; GPL/AGPL code is never imported (tools may be
  *executed*); regenerate hash-locked files with `make -C backend lock` and review the diff.
- A design change that alters a trust boundary needs an ADR (Context / Decision / Alternatives /
  Consequences).

## Adding a database migration

Change the models, then `cd backend && .venv/bin/alembic revision --autogenerate -m "…"`, **review
the generated file**, add anything Alembic cannot infer (triggers, data), and run the migration
tests (`models ≡ migration`, upgrade/downgrade). Never edit a released migration.
