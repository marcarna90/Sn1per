# Jarvis — Orchestration & Reporting Layer for Sn1per

Jarvis is a lightweight, open-source layer that sits **on top of the Sn1per
Community engine**. It turns the raw loot Sn1per collects (nmap XML, sc0pe
vulnerability files, OSINT dumps, discovered subdomains) into presentable,
portable deliverables — the piece the Community edition otherwise leaves to
the paid *Professional* version.

> Jarvis does **not** replace Sn1per. Sn1per does the scanning; Jarvis reads
> what it produced and reports on it.

## Why

In the Community edition, `sniper-report.html` is referenced everywhere but
never actually generated (it is gated behind `pro.sh`), and the old
`bin/report.py` was a broken two-line stub with a hard-coded path. Jarvis
fills that gap with a real reporting engine.

## Design principles

- **Zero dependencies for the core.** Collection and HTML/Markdown/JSON
  rendering use only the Python 3 standard library — no `pip install`
  required. It runs anywhere Sn1per runs.
- **PDF is best-effort.** If WeasyPrint, `wkhtmltopdf`, or a Chromium/Chrome
  binary is present, Jarvis emits a PDF too; otherwise it skips PDF with a
  clear message (the HTML is always printable to PDF from a browser).
- **Parsing and rendering are separated.** The collector normalises loot into
  a small data model (`jarvis/report/model.py`); renderers only ever see that
  model, so new output formats are cheap to add.
- **One-file rebrand.** All naming/colours live in `jarvis/branding.py`.

## Usage

From the Sn1per directory:

```bash
# Generate HTML + Markdown + JSON (default) into <workspace>/reports
./jarvis-cli report -w /usr/share/sniper/loot/workspace/acme

# Choose formats and an output directory, name the engagement
./jarvis-cli report -w loot/workspace/acme -o ./out -f html,md,json,pdf -n "ACME Q4 Pentest"

# Also runnable as a module
PYTHONPATH=. python3 -m jarvis report -w loot/workspace/acme
```

It also runs **automatically** at the end of a Community-edition scan: when
`pro.sh` is absent, `sniper` now calls `jarvis-cli` to produce a report from
the workspace loot.

### Options

| Flag | Description | Default |
| --- | --- | --- |
| `-w, --workspace` | Sn1per loot/workspace directory (required) | — |
| `-o, --out` | Output directory | `<workspace>/reports` |
| `-f, --format` | Comma list of `html,md,json,pdf` | `html,md,json` |
| `-n, --name` | Engagement name | workspace folder name |
| `-q, --quiet` | Suppress the banner | off |

## What it parses

| Loot source | Becomes |
| --- | --- |
| `nmap/nmap-*.xml` | Hosts, open ports, services, OS, MAC |
| `nmap/ports-*.txt` | Fallback port list when no XML is present |
| `vulnerabilities/sc0pe-*.txt` | Findings (`severity, name, location, evidence`) |
| `domains/*-sorted.txt` | Attack surface (subdomains / targets) |
| `osint/*` | OSINT summary |
| `notes/notes.txt` | Scope / engagement notes |

Risk scoring mirrors Sn1per's own sc0pe formula
(`critical×5 + high×4 + medium×3 + low×2 + info×1`) so the numbers line up.

## Tests

```bash
PYTHONPATH=. python3 -m unittest discover -s jarvis/tests -v
```

A small synthetic loot directory lives in `jarvis/tests/fixtures/demo-workspace`
and is safe to use as a reference for the expected loot layout.

## Rebranding

Edit `jarvis/branding.py` — name, tagline, accent colour and severity colours
are all there. Nothing else needs to change.

## Legal

For authorised security testing only. Always have explicit written permission
to test every in-scope target.
