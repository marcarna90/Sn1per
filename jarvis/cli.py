"""Command-line interface for the Jarvis orchestration & reporting layer."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jarvis import branding
from jarvis.report.generate import VALID_FORMATS, generate_reports

BANNER = rf"""
     _   _    ____  __     _____ ____
    | | / \  |  _ \ \ \   / /_ _/ ___|
 _  | |/ _ \ | |_) | \ \ / / | |\___ \
| |_| / ___ \|  _ <   \ V /  | | ___) |
 \___/_/   \_\_| \_\   \_/  |___|____/   v{branding.VERSION}
 {branding.TAGLINE}
 {branding.ENGINE_CREDIT}
"""


def _print_banner() -> None:
    sys.stderr.write(BANNER + "\n")


def _cmd_run(args: argparse.Namespace) -> int:
    from jarvis.orchestrate.config import CampaignError, load_campaign
    from jarvis.orchestrate.executor import DryRunExecutor, SniperExecutor
    from jarvis.orchestrate.runner import run_campaign

    try:
        campaign = load_campaign(args.campaign)
    except CampaignError as exc:
        sys.stderr.write(f"[!] {exc}\n")
        return 2

    if not args.quiet:
        _print_banner()

    workspace_dir = Path(args.loot_base).expanduser() / campaign.workspace
    mode_label = "DRY-RUN" if args.dry_run else "LIVE"
    sys.stderr.write(
        f"[*] Campaign: {campaign.name}  |  workspace: {campaign.workspace}  |  mode: {mode_label}\n"
    )
    sys.stderr.write(
        f"[*] {len(campaign.targets)} target(s), {len(campaign.workflow)} phase(s)\n"
    )
    if not args.dry_run:
        sys.stderr.write(f"[*] Loot/report directory: {workspace_dir}\n")

    def progress(tr) -> None:
        marker = {"done": "+", "failed": "!", "skipped": "-"}.get(tr.status, "*")
        if args.dry_run:
            print(f"[{marker}] would run: {' '.join(tr.task.command)}")
        else:
            print(f"[{marker}] {tr.task.id}: {tr.status} ({tr.note or 'ok'})")

    executor = DryRunExecutor() if args.dry_run else SniperExecutor()
    result = run_campaign(
        campaign,
        executor=executor,
        workspace_dir=None if args.dry_run else str(workspace_dir),
        generate_report=not args.no_report,
        sniper_bin=args.sniper_bin,
        progress=progress,
    )

    sys.stderr.write(
        f"[=] {len(result.tasks)} task(s) executed, {len(result.failed)} failed\n"
    )
    for fmt in VALID_FORMATS:
        if fmt in result.reports:
            print(f"[+] {fmt.upper():5s} -> {result.reports[fmt]}")
    if "pdf_error" in result.reports:
        sys.stderr.write(f"[i] PDF skipped: {result.reports['pdf_error']}\n")
    if "error" in result.reports:
        sys.stderr.write(f"[i] Report skipped: {result.reports['error']}\n")

    return 1 if result.failed else 0


def _cmd_report(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        sys.stderr.write(f"[!] Loot directory not found: {workspace}\n")
        return 2

    out_dir = args.out or (workspace / "reports")
    formats = [f.strip() for f in args.format.split(",") if f.strip()]

    if not args.quiet:
        _print_banner()
        sys.stderr.write(f"[*] Collecting loot from: {workspace}\n")

    try:
        results = generate_reports(
            loot_root=workspace,
            out_dir=out_dir,
            formats=formats,
            name=args.name,
            client=args.client or "",
            logo_path=args.logo,
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"[!] {exc}\n")
        return 2

    for fmt in VALID_FORMATS:
        if fmt in results:
            print(f"[+] {fmt.upper():5s} -> {results[fmt]}")
    if "pdf_error" in results:
        sys.stderr.write(f"[i] PDF skipped: {results['pdf_error']}\n")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jarvis",
        description=f"{branding.LONG_NAME} — {branding.TAGLINE}",
    )
    parser.add_argument(
        "--version", action="version", version=f"{branding.NAME} {branding.VERSION}"
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    report = sub.add_parser(
        "report",
        help="Generate a report (HTML/Markdown/JSON/PDF) from a Sn1per loot directory",
    )
    report.add_argument(
        "-w",
        "--workspace",
        required=True,
        help="Path to a Sn1per loot/workspace directory",
    )
    report.add_argument(
        "-o",
        "--out",
        default=None,
        help="Output directory for reports (default: <workspace>/reports)",
    )
    report.add_argument(
        "-f",
        "--format",
        default="html,md,json",
        help="Comma-separated formats: %s (default: html,md,json)"
        % ",".join(VALID_FORMATS),
    )
    report.add_argument(
        "-n", "--name", default=None, help="Engagement name (default: workspace folder name)"
    )
    report.add_argument("--client", default=None, help="Client name shown on the report")
    report.add_argument("--logo", default=None, help="Path to a client logo image (HTML)")
    report.add_argument("-q", "--quiet", action="store_true", help="Suppress the banner")
    report.set_defaults(func=_cmd_report)

    run = sub.add_parser(
        "run",
        help="Run a campaign (ordered Sn1per workflow) from a JSON/YAML file",
    )
    run.add_argument("campaign", help="Path to a campaign file (.json / .yaml / .yml)")
    run.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the execution plan without launching any scans",
    )
    run.add_argument(
        "--loot-base",
        default="/usr/share/sniper/loot/workspace",
        help="Base directory holding workspace loot (default: %(default)s)",
    )
    run.add_argument(
        "--sniper-bin", default="sniper", help="Path to the sniper binary (default: sniper)"
    )
    run.add_argument(
        "--no-report",
        action="store_true",
        help="Do not generate a report at the end of the campaign",
    )
    run.add_argument("-q", "--quiet", action="store_true", help="Suppress the banner")
    run.set_defaults(func=_cmd_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        _print_banner()
        parser.print_help(sys.stderr)
        return 1
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
