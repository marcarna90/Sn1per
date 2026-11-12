# ADR 0008 — Common normalised findings schema

Status: Accepted

## Context

"Results from different engines must be normalised into a common schema."
Engines (DNS, Nmap, Nuclei, OSINT, web checks) have unrelated native outputs.
Reporting and dashboards must work without knowing which engine produced a row.

## Decision

Every engine yields `NormalisedFinding` objects (Pydantic, `orchestrator/findings.py`)
persisted as rows of `findings`:

| Field | Meaning |
|---|---|
| `category` | `asset`, `dns_record`, `open_port`, `service`, `vulnerability`, `misconfiguration`, `info` |
| `severity` | `info`, `low`, `medium`, `high`, `critical` (one scale for all engines) |
| `title`, `description` | Human-readable, engine-agnostic |
| `asset` | The host/URL/IP the finding is about |
| `evidence` | JSONB: raw, engine-specific proof (kept for reports and audits) |
| `fingerprint` | SHA-256 over `(category, asset, title, canonical evidence key)` — stable across runs |
| `source_engine` | Which allowlisted engine produced it |

- `UNIQUE (scan_id, fingerprint)` de-duplicates within a scan at the database level.
- The stable fingerprint also lets later phases track a finding across scans
  (new / persistent / resolved) without schema changes.
- Severity mapping from each engine's native scale lives **in that engine's
  adapter** (e.g. Nuclei `info..critical` maps 1:1; CVSS bands will map to the
  same five levels), so the rest of the system never sees engine-specific scales.
- Category and severity are text columns guarded by `CHECK` constraints, not
  native PostgreSQL enums: adding a category is a one-line migration with no
  `ALTER TYPE` locking.

## Alternatives rejected

- *One table per engine* — dashboards and reports would need N joins/unions.
- *Store raw tool output only* — pushes parsing into every consumer; no filtering
  by severity in SQL.
- *Adopt an external format (SARIF/OCSF) as the storage schema* — useful as an
  **export** format (Phase 6), too lossy and rigid as the internal model.

## Consequences

Adding an engine means writing one adapter that maps native output to
`NormalisedFinding`; no database change unless a new category is needed.
