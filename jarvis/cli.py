"""Command-line interface for the Jarvis orchestration & reporting layer."""

from __future__ import annotations

import argparse
import os
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


def _cmd_export(args: argparse.Namespace) -> int:
    from jarvis import export as exportmod

    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        sys.stderr.write(f"[!] Workspace not found: {workspace}\n")
        return 2
    reports_dir = Path(args.reports_dir).expanduser() if args.reports_dir else workspace / "reports"

    if not args.quiet:
        _print_banner()

    # --serve just hosts the reports directory for host-side download.
    if args.serve:
        files = exportmod.collect_report_files(reports_dir)
        if not files:
            sys.stderr.write(
                f"[!] No report files in {reports_dir}. Run 'jarvis report' / 'jarvis asm' first.\n"
            )
            return 2
        httpd = exportmod.serve(reports_dir, port=args.port, bind=args.bind)
        ip = exportmod.primary_ip()
        sys.stderr.write(
            f"[*] Serving {reports_dir} ({len(files)} file(s)) over HTTP.\n"
            f"[*] From the HOST browser open:  http://{ip}:{args.port}/\n"
            f"[*] (also http://localhost:{args.port}/ if a port is forwarded)\n"
            f"[*] Press Ctrl+C to stop.\n"
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            sys.stderr.write("\n[*] Stopped.\n")
        finally:
            httpd.server_close()
        return 0

    # Otherwise: build a single portable zip bundle.
    try:
        archive = exportmod.bundle(
            workspace=workspace, out=args.out, reports_dir=reports_dir, name=args.name
        )
    except FileNotFoundError as exc:
        sys.stderr.write(f"[!] {exc}\n")
        return 2
    print(f"[+] Bundle: {archive}")

    if args.to:
        try:
            copied = exportmod.copy_to(archive, args.to)
            print(f"[+] Copied to: {copied}")
        except OSError as exc:
            sys.stderr.write(f"[!] Copy to {args.to} failed: {exc}\n")
            return 1
    return 0


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
        resume=args.resume,
    )

    skipped = sum(1 for t in result.tasks if t.status == "skipped")
    sys.stderr.write(
        f"[=] {len(result.tasks)} task(s): "
        f"{len(result.tasks) - len(result.failed) - skipped} done, "
        f"{skipped} skipped, {len(result.failed)} failed\n"
    )
    for fmt in VALID_FORMATS:
        if fmt in result.reports:
            print(f"[+] {fmt.upper():5s} -> {result.reports[fmt]}")
    if "pdf_error" in result.reports:
        sys.stderr.write(f"[i] PDF skipped: {result.reports['pdf_error']}\n")
    if "error" in result.reports:
        sys.stderr.write(f"[i] Report skipped: {result.reports['error']}\n")

    webhook = args.slack_webhook or os.environ.get("SLACK_WEBHOOK", "")
    if webhook and not args.dry_run:
        from jarvis.orchestrate.notifications import send_slack, summarize

        ok = send_slack(webhook, summarize(result))
        sys.stderr.write(
            f"[i] Slack notification {'sent' if ok else 'failed'}\n"
        )

    return 1 if result.failed else 0


def _cmd_schedule(args: argparse.Namespace) -> int:
    from jarvis.orchestrate.schedule import build_cron_line, cron_expression

    repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        cron_expression(args.cadence, args.cron)  # validate early
        line = build_cron_line(
            campaign_path=args.campaign,
            repo_dir=repo_dir,
            loot_base=args.loot_base,
            cadence=args.cadence,
            custom_cron=args.cron,
            sniper_bin=args.sniper_bin,
        )
    except ValueError as exc:
        sys.stderr.write(f"[!] {exc}\n")
        return 2

    if args.install:
        import subprocess

        try:
            current = subprocess.run(
                ["crontab", "-l"], capture_output=True, text=True
            ).stdout
        except (FileNotFoundError, OSError):
            sys.stderr.write("[!] 'crontab' not available; printing the line instead.\n")
            print(line)
            return 1
        if line in current:
            sys.stderr.write("[i] Schedule already installed.\n")
            return 0
        new = (current.rstrip("\n") + "\n" + line + "\n").lstrip("\n")
        proc = subprocess.run(["crontab", "-"], input=new, text=True)
        if proc.returncode == 0:
            sys.stderr.write("[+] Installed crontab entry:\n")
            print(line)
            return 0
        sys.stderr.write("[!] Failed to install crontab entry.\n")
        return 1

    print(line)
    return 0


def _cmd_asm(args: argparse.Namespace) -> int:
    from jarvis.asm.generate import VALID_FORMATS as ASM_FORMATS
    from jarvis.asm.generate import generate_asm_reports

    workspace = Path(args.workspace).expanduser()
    if not workspace.is_dir():
        sys.stderr.write(f"[!] Loot directory not found: {workspace}\n")
        return 2

    out_dir = args.out or (workspace / "reports")
    formats = [f.strip() for f in args.format.split(",") if f.strip()]

    if not args.quiet:
        _print_banner()
        sys.stderr.write(f"[*] Building attack surface from: {workspace}\n")

    try:
        results = generate_asm_reports(
            loot_root=workspace,
            out_dir=out_dir,
            formats=formats,
            name=args.name,
            client=args.client or "",
            executive=not args.no_executive,
            live=args.live,
            diff=args.diff,
            snapshot=not args.no_snapshot,
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"[!] {exc}\n")
        return 2

    order = ["html", "html_exec", "md", "json", "pdf", "pdf_exec"]
    labels = {
        "html": "HTML (technical)", "html_exec": "HTML (executive)",
        "md": "Markdown", "json": "JSON", "pdf": "PDF (technical)",
        "pdf_exec": "PDF (executive)",
    }
    for key in order:
        if key in results:
            print(f"[+] {labels[key]:18s} -> {results[key]}")
    if "pdf_error" in results:
        sys.stderr.write(f"[i] PDF skipped: {results['pdf_error']}\n")
    return 0


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
    run.add_argument(
        "--resume",
        action="store_true",
        help="Skip tasks already marked done in the workspace campaign state",
    )
    run.add_argument(
        "--slack-webhook",
        default=None,
        help="Slack incoming-webhook URL for an end-of-campaign summary "
        "(or set SLACK_WEBHOOK)",
    )
    run.add_argument("-q", "--quiet", action="store_true", help="Suppress the banner")
    run.set_defaults(func=_cmd_run)

    asm = sub.add_parser(
        "asm",
        help="Generate an External Attack Surface Management report from loot",
    )
    asm.add_argument("-w", "--workspace", required=True, help="Sn1per loot/workspace directory")
    asm.add_argument("-o", "--out", default=None, help="Output directory (default: <workspace>/reports)")
    asm.add_argument(
        "-f", "--format", default="html,md,json",
        help="Comma-separated formats: html,md,json,pdf (default: html,md,json)",
    )
    asm.add_argument("-n", "--name", default=None, help="Engagement name (default: workspace folder name)")
    asm.add_argument("--client", default=None, help="Client name shown on the report")
    asm.add_argument(
        "--no-executive", action="store_true",
        help="Do not also produce the one-page executive report",
    )
    asm.add_argument(
        "--live", action="store_true",
        help="Perform live DNS (SPF/DMARC), TLS certificate and typosquat checks on in-scope assets",
    )
    asm.add_argument(
        "--diff", action="store_true",
        help="Include a 'changes since last scan' section (vs the most recent snapshot)",
    )
    asm.add_argument(
        "--no-snapshot", action="store_true",
        help="Do not save a snapshot of this run for future diffs",
    )
    asm.add_argument("-q", "--quiet", action="store_true", help="Suppress the banner")
    asm.set_defaults(func=_cmd_asm)

    sched = sub.add_parser(
        "schedule",
        help="Print (or install) a crontab line that re-runs a campaign periodically",
    )
    sched.add_argument("campaign", help="Path to the campaign file")
    sched.add_argument(
        "--cadence",
        choices=["daily", "weekly", "monthly"],
        default="daily",
        help="Schedule cadence (default: daily)",
    )
    sched.add_argument(
        "--cron", default=None, help="Custom 5-field cron expression (overrides --cadence)"
    )
    sched.add_argument(
        "--loot-base",
        default="/usr/share/sniper/loot/workspace",
        help="Base directory holding workspace loot (default: %(default)s)",
    )
    sched.add_argument("--sniper-bin", default="sniper", help="Path to the sniper binary")
    sched.add_argument(
        "--install", action="store_true", help="Append the line to the current user's crontab"
    )
    sched.set_defaults(func=_cmd_schedule)

    export = sub.add_parser(
        "export",
        help="Export a workspace's reports off the VM/container (zip bundle or HTTP)",
    )
    export.add_argument("-w", "--workspace", required=True, help="Sn1per loot/workspace directory")
    export.add_argument(
        "--reports-dir", default=None,
        help="Directory holding the reports (default: <workspace>/reports)",
    )
    export.add_argument(
        "-o", "--out", default=None,
        help="Output .zip path or directory for the bundle (default: the workspace dir)",
    )
    export.add_argument(
        "--to", default=None,
        help="Also copy the bundle to this directory (e.g. a mounted shared folder)",
    )
    export.add_argument(
        "--serve", action="store_true",
        help="Serve the reports over HTTP for host-side download instead of zipping",
    )
    export.add_argument("--port", type=int, default=8000, help="Port for --serve (default: 8000)")
    export.add_argument("--bind", default="0.0.0.0", help="Bind address for --serve (default: 0.0.0.0)")
    export.add_argument("-n", "--name", default=None, help="Bundle name (default: workspace folder name)")
    export.add_argument("-q", "--quiet", action="store_true", help="Suppress the banner")
    export.set_defaults(func=_cmd_export)

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
