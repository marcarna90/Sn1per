# End-to-end smoke test (real processes, no Docker)

`run.sh` starts the **real** stack as separate processes and drives it over HTTP and with a real
browser. It exists because unit and integration tests cannot show that the pieces work *together*
(its first run found a bug the 74 frontend unit tests missed — see CHANGELOG).

| Process | Role |
|---|---|
| `fake_dns.py` | Authoritative UDP DNS server answering from a JSON file re-read on every query, so a test can flip an answer (DNS rebinding) and read which names were looked up. Reached through `NEO_DNS_NAMESERVERS`. |
| uvicorn | The FastAPI app (`create_app --factory`) |
| Celery worker | Started and stopped by `worker_ctl.sh` (the tests stop it to queue scans and to flip DNS) |
| nginx | The real `frontend/nginx/default.conf` with only paths/ports substituted, serving `frontend/dist` and proxying `/api` |
| PostgreSQL, Redis | Provided by you (an empty database, a dedicated Redis DB) |

```bash
# one-off: an empty database and a dedicated Redis DB
createdb neo_e2e                       # owned by the role in the URL below
export NEO_E2E_DATABASE_URL='postgresql+pg8000://neo:...@127.0.0.1:5432/neo_e2e'
export NEO_E2E_REDIS_URL='redis://127.0.0.1:6379/14'

make -C backend install && (cd frontend && npm ci)   # once
make e2e                                              # = ./e2e/run.sh ; exit status 0 = all green
```

Needs: the backend venv, Node + Playwright with Chromium (`require('playwright')` must resolve),
`nginx`, `curl`, and permission to bind `127.0.0.77:53` (UDP) and ports 8000/8080 (override with
`E2E_DNS_ADDRESS`, `E2E_API_PORT`, `E2E_WEB_PORT`). Logs and screenshots go to `E2E_WORKDIR`
(a temporary directory unless set); `E2E_SKIP_BROWSER=1` skips the browser part.

## What it checks

- **`smoke.py` (API, 94 checks):** health through nginx, `/metrics` hidden by nginx, CSP and other
  headers, cache headers; login/refresh/logout over nginx, cookie flags, CSRF header, refresh
  rotation and **reuse detection**, forged/tampered tokens; scope rules (hard-denied ranges cannot
  be authorised; refused targets; **no DNS lookup for unauthorised names**); a scan executed by the
  real worker (findings, DNS evidence); injection-shaped targets and parameters; **DNS rebinding
  while a scan is queued → `failed / scope_denied` at execution**; cancelling a queued scan;
  organisation isolation (404), RBAC, account lockout; audit trail (denials included, no secrets)
  and the **database trigger refusing UPDATE/DELETE/TRUNCATE** on the audit table; nginx 429 limiter.
- **`browser_smoke.cjs` (UI, 22 checks):** login screen and generic error, cookie flags, no token in
  web storage, authorising a domain, dry-run, out-of-scope refusal, a scan followed to « Terminé »
  with its findings, reload keeping the session, 375 px layout without horizontal scroll, logout,
  and **zero CSP violations / console errors / unexpected HTTP errors**. Screenshots are saved.

## What it does not prove

- The Docker images and Compose file are **not** exercised (the host's nginx and Python are used).
- No TLS: the e2e runs in `NEO_ENV=development` with `NEO_COOKIE_SECURE=false`; production-mode
  guards are covered by unit tests only.
- DNS answers are fake and nothing ever connects to a scanned address (the only engine, `dns_recon`,
  only queries DNS). Nmap/Nuclei engines do not exist yet.
- It is not wired into CI yet (it needs a DNS port on loopback and a Chromium); do that when the
  images build in CI.
