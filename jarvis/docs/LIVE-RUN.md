# Jarvis — Live-run validation runbook

This checklist validates Jarvis against a **real** Sn1per installation. It is
written for a Kali/Parrot box (or the Sn1per Docker image) with Sn1per
installed and run as root. None of it can be exercised in a sandbox without
Sn1per + root, so it lives here as a reproducible procedure.

> Only run scans against targets you are explicitly authorised to test.

## 0. Prerequisites

```bash
# Sn1per installed (bash install.sh) and on PATH as 'sniper'
which sniper
# Python 3 present (Jarvis needs nothing else for HTML/MD/JSON)
python3 --version
# Optional, for PDF: one of these
which wkhtmltopdf || which chromium || python3 -c "import weasyprint" 2>/dev/null
```

## 1. Report engine against an existing workspace

```bash
# Pick any workspace you already scanned:
sniper --list
# Generate every format:
./jarvis-cli report -w /usr/share/sniper/loot/workspace/<WORKSPACE> -f html,md,json,pdf
```

**Expect:** `<WORKSPACE>/reports/<name>-report.{html,md,json,pdf}`. Open the
HTML; the host, port and finding counts must match what you see under
`loot/workspace/<WORKSPACE>/`.

**Spot-checks:**
- Host/port counts equal `cat nmap/ports-*.txt | sort -u | wc -l` (roughly).
- Risk score equals `cat vulnerabilities/vuln_score_total.txt` (same formula).
- sc0pe findings all appear in the Findings table.

## 2. Automatic report at end of a Community scan

```bash
sniper -t scanme.nmap.org -w jarvis-smoke
```

**Expect:** after the scan, a line
`[*] Jarvis report saved to: .../jarvis-smoke/reports/...-report.html` and the
report opens in `$BROWSER`. (This only triggers when `pro.sh` is absent.)

## 3. Orchestration — dry-run first (no root needed)

```bash
./jarvis-cli run jarvis/examples/campaign.json --dry-run
```

**Expect:** the exact `sniper ...` command lines that would run, in phase
order, with the right flags. Nothing is launched.

## 4. Orchestration — live campaign

```bash
# Edit the example to point at authorised targets, then:
./jarvis-cli run campaign.yaml --loot-base /usr/share/sniper/loot/workspace
```

**Expect:**
- Phases run in order; tasks within a phase run in parallel.
- `loot/workspace/<workspace>/scans/jarvis-campaign-state.json` updates after
  each phase (tail it from another shell to watch progress).
- A consolidated report lands in `<workspace>/reports/` at the end.
- `[=] N task(s) executed, M failed` summarises the run; non-zero exit if any
  task failed.

## 5. Resume after interruption

Interrupt a live campaign (Ctrl-C), then re-run the same command with
`--resume`. **Expect:** phases/tasks already marked `done` in the state file
are skipped and only the remainder runs.

## Troubleshooting

| Symptom | Likely cause |
| --- | --- |
| `sniper binary not found` | `--sniper-bin /full/path/to/sniper` or add to PATH |
| Empty report | wrong `-w` path, or scan wrote no loot yet |
| PDF skipped | install wkhtmltopdf / chromium / weasyprint (HTML still prints to PDF) |
| YAML error | `pip install pyyaml` or use the JSON campaign form |
