# Operations guide

## Deploy

```bash
cp .env.example .env            # NEO_SECRET_KEY, POSTGRES_PASSWORD, REDIS_PASSWORD (required)
docker compose up -d --build    # db, redis, migrate (one-shot), api, worker, web
docker compose ps               # all services healthy?
make create-org NAME="Acme" SLUG=acme EMAIL=admin@acme.example.com
```

- **TLS.** Terminate HTTPS in a reverse proxy in front of `web` (port `127.0.0.1:8080`), set
  `Strict-Transport-Security` there, and keep `NEO_COOKIE_SECURE=true` (the default; production mode
  refuses otherwise). Forward `X-Forwarded-For`/`-Proto`.
- **Network.** Nothing but `web` is published. PostgreSQL and Redis are reachable only on the
  Compose network. Do not expose them.
- **Workers egress.** Workers must reach scan targets and DNS. Restrict everything else with host
  or network policy (no access to your internal admin networks unless they are in scope).
- **Scaling.** `docker compose up -d --scale worker=3`. Each worker runs 2 processes; one scan
  occupies one process.

## Upgrade

1. `make backup`
2. `git pull && docker compose build`
3. `docker compose up -d` — the `migrate` one-shot runs `alembic upgrade head` before `api` and
   `worker` start (`depends_on: service_completed_successfully`).
4. Check `docker compose ps` and `GET /health/ready`.

Migrations are forward-only in production; each has a tested `downgrade` for development.
Ideally run `migrate` with a database role that owns the schema and run `api`/`worker` with a role
that does **not** (it limits what a compromised app credential can do, notably disabling the
audit triggers — see ADR 0006).

## Backup and restore

```bash
make backup                                   # → backups/neo-<UTC>.sql.gz  (mode 0600, git-ignored)
docker compose stop api worker
./scripts/restore.sh backups/neo-….sql.gz     # DESTRUCTIVE, asks for confirmation
docker compose start api worker
```

The dump contains the audit log and password hashes: protect it like the database, encrypt it at
rest, and copy it off-host. Test restores regularly — an untested backup is a hope. Redis only holds
the queue (AOF is enabled so queued scans survive a restart); scan results live in PostgreSQL.

## Secrets

| Secret | Rotation |
|---|---|
| `POSTGRES_PASSWORD`, `REDIS_PASSWORD` | Change in `.env` **and** in the running service, then restart `api` and `worker` |
| `NEO_SECRET_KEY` | Change in `.env`, restart `api` and `worker`. **All sessions are invalidated** (single signing key; ADR 0005) |

`.env` is git-ignored; never commit it, paste it in tickets, or bake it into images.

## Monitoring

- **Health:** `/health/live` (process), `/health/ready` (database + Redis; 503 when degraded).
- **Metrics:** the API exposes Prometheus metrics at `/metrics` *inside* the Compose network (nginx
  answers 404 for `/metrics`). Scrape `api:8000/metrics`. Metrics: `neo_http_requests_total`,
  `neo_http_request_duration_seconds` (labels use route templates). Disable with
  `NEO_METRICS_ENABLED=false`.
- **Logs:** JSON on stdout (`docker compose logs api worker`). Every API line has `request_id`
  (also returned as `X-Request-ID` and in error bodies) — quote it when reporting a problem.
  Notable events: `scan.finished`, `scan.engine_crashed`, `health.*_unavailable`.
- **Audit:** `GET /api/v1/audit-logs` (admins). Alert on `auth.refresh_reuse_detected`, repeated
  `auth.login` denials, and `scan.create` / `scan.finish` denials.

## Hardening checklist

- [ ] TLS in front, HSTS set, `NEO_COOKIE_SECURE=true`
- [ ] Strong random `NEO_SECRET_KEY`, `POSTGRES_PASSWORD`, `REDIS_PASSWORD`; `.env` mode 0600
- [ ] Rate limiting / WAF on `/api/v1/auth/*` at the edge (the app has account lockout only)
- [ ] `api`/`worker` use a database role that does not own the tables
- [ ] Worker egress restricted; no route from workers to management networks
- [ ] Backups encrypted, off-host, restore tested
- [ ] `NEO_CORS_ORIGINS` empty (same-origin UI) unless a separate UI origin is required
- [ ] Images pinned by digest and rebuilt regularly; Dependabot/Renovate enabled
- [ ] Only admins are admins; review `users` and the audit log periodically

## Troubleshooting

| Symptom | Check |
|---|---|
| `docker compose up` stops: "required variable … is missing" | Fill the named variable in `.env` |
| Login works, then immediately logged out | Plain HTTP with `NEO_COOKIE_SECURE=true`: use HTTPS, or for local evaluation only `NEO_ENV=development` + `NEO_COOKIE_SECURE=false` |
| `POST /scans` → 503 `service_unavailable` | Redis down or unreachable (`/health/ready`); the scan is recorded as `failed/dispatch_failed` |
| Scan fails with `scope_denied` | The target no longer matches an authorisation (rule deleted, or DNS now resolves outside scope — possibly rebinding). See the scan's `scope_decision` |
| Scan stuck in `running` | See *Known limitations* (no reaper); cancel it, or check worker logs / restart workers |
| `429` on login | nginx rate limit on `/api/v1/auth/` (10/min per IP, burst 20) |

## Known limitations

- **Images verified once, outside CI.** The images were built and the full stack (db, redis,
  migrate, api, worker, web) was run with Docker Engine 29 / Compose v5 in the authoring sandbox
  (2026-11-15), and the e2e suites (94 API + 22 browser checks) passed against it. That run needed the
  sandbox's TLS-proxy certificate injected into a scratch copy of the Dockerfiles (not in the repo).
  Never exercised: the GitHub Actions workflow itself, Docker Desktop on Windows/macOS, and
  production TLS. Base images are tags, not digests. `db` and `redis` are the official images with
  their default (root entrypoint) settings: only `api`, `worker` and `web` are read-only, non-root and
  capability-free.
- **The e2e suite is not in CI** and does not exercise the Docker images (it runs the same code
  with host processes); see `e2e/README.md`.
- **No stale-scan reaper.** If a worker dies and Redis loses the message, a scan can stay `running`
  forever (ADR 0007).
- **No per-organisation concurrency limits or priorities.**
- **Single signing key**, no key rotation window; no MFA/SSO; no absolute session lifetime (ADR 0005).
- **No public-suffix validation** for domain authorisations (ADR 0004).
- **Account lockout can be abused** to lock a known account out; mitigate with edge rate limiting.
- **Audit triggers** do not stop a database *owner* from disabling them (ADR 0006).
- Colour contrast and real screen-reader behaviour of the UI are not covered by automated tests
  (ADR 0009).
