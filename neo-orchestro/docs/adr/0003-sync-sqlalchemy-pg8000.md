# ADR 0003 — Synchronous SQLAlchemy 2 with `pg8000`

Status: Accepted

## Context

Stack: PostgreSQL + SQLAlchemy + Alembic. Two consumers share the same models:
FastAPI and Celery workers. Celery tasks are synchronous prefork processes.
The audit left the driver open: `psycopg` (LGPL-3.0) or `asyncpg` (Apache-2.0).

## Decision

Use **synchronous SQLAlchemy 2.x** with the **`pg8000`** driver (pure Python,
BSD-3-Clause).

- One session model, one set of repositories, used identically by API
  (FastAPI runs sync endpoints in a threadpool) and workers.
- No copyleft in the dependency tree; no C extension to build in images.
- Spike (2026-11-12, PostgreSQL 16.15 + SQLAlchemy 2.1.8 + pg8000 1.31.6)
  verified: UUID, JSONB, text-backed enums, `timestamptz`, unicode round-trip,
  and exceptions raised from `plpgsql` triggers.

## Alternatives rejected

- *asyncpg* — would force either async everywhere or an `asyncio.run` bridge
  inside every Celery task (event-loop and engine-lifecycle hazards) and two
  code paths for the same repositories.
- *psycopg 3* — mature and fast, but LGPL-3.0. Usable as an unmodified
  dynamically imported library, yet it adds a licence question we can avoid at
  no functional cost here. Revisit if profiling shows the driver is a
  bottleneck (the migration is a connection-URL change).

## Consequences

- Slightly lower raw throughput than psycopg/asyncpg; irrelevant for this
  workload (scan orchestration is I/O-bound on external tools).
- Connection pooling is configured explicitly (`pool_pre_ping`, bounded pool);
  workers use a small pool per process.
- Tests run against a **real PostgreSQL** (no SQLite shortcuts) because we rely
  on JSONB, triggers and constraints.
