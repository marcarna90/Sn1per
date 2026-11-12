# ADR 0010 — Dependency management and licence policy

Status: Accepted

## Context

"No dependency without justification; verify licences of integrated engines."
Security tooling is a supply-chain target. Builds must be reproducible.

## Decision

1. **Reproducible installs.** Direct dependencies are declared with bounded
   ranges in `backend/pyproject.toml`; `pip-compile --generate-hashes
   --allow-unsafe` produces `requirements.txt` (runtime) and
   `requirements-dev.txt`. Installs use `pip install --require-hashes`
   (Makefile, Dockerfile, CI). Frontend uses `package-lock.json` + `npm ci`.
2. **Licence gate.** Every dependency (transitive included) is checked at lock
   time; the full tree is recorded in `docs/licences.md`. Allowed: MIT, BSD,
   ISC, Apache-2.0, PSF, Unlicense/CC0, MIT-0. **Not imported:** GPL, AGPL,
   SSPL, Commons-Clause. LGPL only with an explicit ADR (none today).
3. **GPL/AGPL *tools* are executed, never imported.** Nmap, for instance, is
   invoked as a separate process with an argv list (ADR 0007) and its XML
   output is parsed with a safe parser; we do **not** use `python-nmap`
   (GPL-3.0). Detection content (e.g. Nuclei templates) is verified per source
   when integrated, and recorded in `docs/licences.md`.
4. **Vulnerability gate.** `pip-audit` (and `npm audit`) run in CI; a known
   vulnerability in the runtime lock fails the build.
5. **Justification** for each direct dependency lives in `docs/licences.md`.

## Alternatives rejected

- *Unpinned ranges only* — non-reproducible, unsafe for a security product.
- *Poetry/uv* — fine tools, but `pip-tools` keeps the toolchain to plain `pip`
  (available everywhere, trivially auditable). Revisit if lock times hurt.

## Consequences

- Dependency bumps are deliberate (`make lock`, review the diff, run
  `make check`). Dependabot/Renovate can automate this later.
- Verified on 2026-11-12: 46 runtime packages, 0 flagged licences,
  `pip-audit`: no known vulnerabilities.
