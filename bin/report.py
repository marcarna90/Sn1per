#!/usr/bin/env python3
"""Legacy report helper — now a thin wrapper around the Jarvis engine.

Historically this file was a two-line ``pdfkit`` snippet with a hard-coded
loot path, which only worked on one developer's machine. It now delegates to
the Jarvis reporting layer, which collects a Sn1per loot directory and emits
HTML / Markdown / JSON / PDF with no external dependencies required.

Usage:
    report.py <loot_or_workspace_dir> [output_dir] [formats]

Examples:
    report.py /usr/share/sniper/loot/workspace/acme
    report.py /usr/share/sniper/loot/workspace/acme ./out html,pdf

Prefer the first-class entry point when you can:  ``jarvis-cli report -w <dir>``
"""

import os
import sys

# Make the repo root importable whether this is run from the repo or from
# the installed location (/usr/share/sniper).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
for _candidate in ("/usr/share/sniper",):
    if os.path.isdir(os.path.join(_candidate, "jarvis")) and _candidate not in sys.path:
        sys.path.insert(0, _candidate)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 1

    loot_dir = argv[0]
    out_dir = argv[1] if len(argv) > 1 else os.path.join(loot_dir, "reports")
    formats = (argv[2] if len(argv) > 2 else "html,md,json").split(",")

    try:
        from jarvis.report.generate import generate_reports
    except ImportError:
        sys.stderr.write(
            "[!] Could not import the Jarvis engine. Run via 'jarvis-cli report' "
            "from the Sn1per directory, or ensure the 'jarvis' package is present.\n"
        )
        return 1

    results = generate_reports(loot_dir, out_dir, formats=[f.strip() for f in formats])
    for fmt, path in results.items():
        if fmt == "pdf_error":
            sys.stderr.write(f"[i] PDF skipped: {path}\n")
        else:
            print(f"[+] {fmt.upper()} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
