# Neo-Orchestro

**Automated Security Assessment & Orchestration Platform**
*Designed & Developed by Ronald TSR.*

Neo-Orchestro orchestrates security assessments (recon, port scanning,
vulnerability assessment, OSINT, web/TLS checks, reporting) behind a modern web
UI, with a strict, auditable scope policy: **nothing runs against a target that
has not been explicitly authorised.**

> **Status: foundations (v0.1.0).** Authentication, RBAC, scope engine,
> asynchronous orchestrator and a first recon engine are implemented. Nmap,
> Nuclei, OSINT and reporting engines follow the roadmap below.
> **Use only on systems you are authorised to test.**

## Documentation

- [`CLAUDE.md`](CLAUDE.md) — working contract (rules, layout, commands)
- [`docs/adr/`](docs/adr/README.md) — every architectural decision, with alternatives
- [`docs/licences.md`](docs/licences.md) — dependencies and licences

## Roadmap

1. Foundations, authentication, database, RBAC, scopes ← *this release*
2. Orchestrator and reconnaissance ← *engine framework + `dns_recon` delivered*
3. Nmap and asset management
4. Nuclei and vulnerability normalisation
5. OSINT and web controls
6. Reporting (PDF/HTML/JSON) and dashboards
7. Security testing, optimisation, publication

*(Quick start, architecture overview and operations guide are completed in the
final documentation step.)*
