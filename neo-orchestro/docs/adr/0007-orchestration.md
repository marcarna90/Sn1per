# ADR 0007 — Asynchronous orchestration: Celery/Redis, engine allowlist, safe execution

Status: Accepted

## Context

All scans must go through an asynchronous orchestrator with cancellation, resumption and
history, and engines must run with argument separation, an allowlist and resource limits —
never a shell command built from user input. Scanners are the riskiest code in the system.

## Decision

**Flow.** `POST /scans` → validate engine (allowlist) and parameters → **scope pre-check**
→ persist `pending` (who/what/when/params/scope snapshot) → publish **only the scan id** to
Redis → a worker runs it → normalised findings are written to PostgreSQL. The broker never
carries target or parameters, so a poisoned queue cannot inject them; the worker reads them
from the database.

**Engines** (`neo_orchestro.engines`) implement a small port (`name`, `target_kinds`,
`validate_params`, `run(ctx) -> findings`). They are an **explicit allowlist registered in
code** (`default_registry`); an engine name from a request is only ever a lookup key —
`nmap`, `dns_recon; rm -rf /`, `../x` are all "unknown engine". Shipped: `dns_recon`
(records + missing-SPF check). External tools run only through `run_command`:
argv list (a string is refused), no shell, fixed `PATH`, minimal environment (no secrets),
closed stdin, own process group killed on timeout/cancel/exit, CPU/memory/file-size limits,
bounded output. Target values are safe to pass as arguments because validated targets can
never start with `-`.

**Runner invariants** (`orchestrator/runner.py`):
1. *Atomic claim*: `UPDATE … WHERE status IN (pending, running) AND cancel_requested_at IS
   NULL AND attempts < 3 … RETURNING` — finished, cancelled or over-retried scans are never
   (re)started, so Celery's at-least-once delivery is safe.
2. *Scope re-validated at execution* (fresh DNS, current rules): rebinding or a deleted
   rule between request and run stops the scan (`scope_denied`, audited as denied). Engines
   receive the **pinned IPs** from that decision.
3. *Cooperative cancellation* through `ctx.check()` (polls the database), plus a hard
   deadline (`NEO_SCAN_MAX_DURATION_SECONDS`).
4. *Partial results are kept*: findings are persisted in batches and de-duplicated by
   fingerprint, so a scan resumed after a crash does not duplicate them.
5. *Classified errors*: expected failures carry a stable code (`dns_error`, `timeout`,
   `too_many_findings`…); anything unexpected is logged with its traceback but stored as a
   generic message (no internals leak). A findings cap stops runaway engines.

**Celery** is hardened: JSON only (no pickle), `acks_late` + `reject_on_worker_lost`,
prefetch 1, no result backend, hard/soft time limits above the engine deadline, and a Redis
`visibility_timeout` above the maximum scan duration so a live scan is never redelivered.
Queue publishing has a bounded retry so an API request fails fast (503) if Redis is down; the
scan is recorded as `failed/dispatch_failed`.

**Cancellation.** A queued scan is cancelled by a conditional SQL transition (it cannot
overwrite a scan a worker just started); a running scan gets `cancel_requested_at` and stops at
its next checkpoint.

## Known limits (open)

- **No reaper.** If a worker dies *and* Redis loses the message, a scan can stay `running`
  forever. Redelivery (AOF-persisted Redis) plus the attempt cap covers the normal cases; a
  periodic "stale running" sweeper is the follow-up.
- No per-organisation concurrency limits or priorities yet (fairness between tenants).
- Redis durability is a deployment concern (enable AOF, protect with a password, do not
  expose it). Workers should run non-root with restricted egress; engines needing raw sockets
  (Nmap SYN scans) should get `CAP_NET_RAW` only, never root.
- `dns_recon` queries DNS *about* the target and does not connect to it; engines that do
  connect must use `pinned_ips` (ADR 0004).

## Alternatives rejected

- *Threads/BackgroundTasks in the API process* — no isolation, no resumption, dies with the
  web worker.
- *RQ/Dramatiq* — fine libraries, but Celery is the required stack and has the mature
  acks/limits/retry semantics needed here.
- *Passing target/params in the task payload* — widens the injection surface for no benefit.
