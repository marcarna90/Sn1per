# ADR 0001 — Independent implementation in an isolated tree

Status: Accepted

## Context

The repository that hosts this work is a fork of Sn1per Community Edition. Its
`LICENSE.md` forbids renaming/rebranding the project (clause 2), creating a
product or service from any part of the code, free or paid (clause 3), and
re-licensing the code (clause 4). It also vendors third-party files under
Apache-2.0, LGPL and GPL, and one file with no licence at all (see the audit).
Neo-Orchestro is a different product with a different name and licence.

## Decision

1. Neo-Orchestro is a **clean, independent implementation**, inspired only by
   *capabilities* (recon, port scanning, vulnerability assessment, OSINT,
   reporting), which are ideas and not protected expression.
2. **No Sn1per code, templates, wordlists or scripts are copied or
   translated.** Detection content will come from permissively licensed
   upstream projects used as separate tools (e.g. Nuclei templates), with
   licences verified at integration time.
3. All code lives under `neo-orchestro/`, self-contained (own CI, docs,
   `.gitignore`, `CLAUDE.md`). Nothing outside this directory is modified.
4. The directory is extractable to its own repository with history:
   `git subtree split --prefix=neo-orchestro -b neo-orchestro-only`.

## Alternatives rejected

- *Port Sn1per to Python/FastAPI* — derivative work, forbidden by the EULA.
- *Replace the fork's contents* — destroys existing work without validation.
- *New repository from day one* — preferred long-term (audit option A), but
  this session has access to one repository only. The subtree split makes the
  move a non-event.

## Consequences

- Licence risk is reduced to "co-located in a repository governed by another
  EULA"; moving to a dedicated repository removes it entirely. **Do this
  before the first public release.**
- A project licence for Neo-Orchestro has not been chosen yet (owner decision);
  until then the code is "all rights reserved — Ronald TSR".
