"""Render an engagement to a clean Markdown report."""

from __future__ import annotations

from jarvis import branding
from jarvis.report.model import SEVERITY_ORDER, Engagement


def _esc(text: str) -> str:
    """Escape pipe characters so free text does not break Markdown tables."""
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def render(engagement: Engagement) -> str:
    counts = engagement.severity_counts()
    lines: list[str] = []
    a = lines.append

    a(f"# {branding.NAME} — Security Assessment Report")
    a("")
    a(f"**Engagement:** {engagement.name}  ")
    a(f"**Generated:** {engagement.generated_at}  ")
    a(f"**Risk rating:** {engagement.risk_rating} (score {engagement.risk_score})  ")
    a(f"**Loot source:** `{engagement.loot_root}`")
    a("")

    # --- Executive summary ------------------------------------------------
    a("## Executive summary")
    a("")
    a(
        f"The assessment identified **{len(engagement.hosts)} live host(s)**, "
        f"**{engagement.total_open_ports} open port(s)** and "
        f"**{len(engagement.vulnerabilities)} finding(s)**. "
        f"The overall risk rating is **{engagement.risk_rating}**."
    )
    a("")
    a("| Severity | Count |")
    a("| --- | --- |")
    for sev in SEVERITY_ORDER:
        a(f"| {sev.capitalize()} | {counts[sev]} |")
    a(f"| **Total** | **{len(engagement.vulnerabilities)}** |")
    a("")

    # --- Findings ---------------------------------------------------------
    a("## Findings")
    a("")
    if engagement.vulnerabilities:
        a("| Severity | Finding | Location | Evidence |")
        a("| --- | --- | --- | --- |")
        for v in engagement.vulnerabilities_sorted():
            a(
                f"| {v.severity.capitalize()} | {_esc(v.name)} | "
                f"{_esc(v.location)} | {_esc(v.evidence)} |"
            )
    else:
        a("_No vulnerabilities were parsed from the loot directory._")
    a("")

    # --- Hosts ------------------------------------------------------------
    a("## Hosts & services")
    a("")
    if engagement.hosts:
        for host in engagement.hosts:
            title = host.target or host.ip or "unknown"
            a(f"### {title}")
            meta = []
            if host.ip and host.ip != title:
                meta.append(f"IP: `{host.ip}`")
            if host.os:
                meta.append(f"OS: {host.os}")
            if host.mac:
                meta.append(f"MAC: {host.mac}")
            if meta:
                a(" · ".join(meta))
                a("")
            if host.open_ports:
                a("| Port | Proto | Service | Details |")
                a("| --- | --- | --- | --- |")
                for p in sorted(host.open_ports, key=lambda x: x.number):
                    a(
                        f"| {p.number} | {p.protocol} | {_esc(p.service)} | "
                        f"{_esc(p.service_banner)} |"
                    )
            else:
                a("_No open ports recorded._")
            a("")
    else:
        a("_No hosts were parsed from the loot directory._")
    a("")

    # --- Attack surface ---------------------------------------------------
    if engagement.subdomains:
        a("## Attack surface (subdomains / targets)")
        a("")
        a(f"{len(engagement.subdomains)} entry(ies) discovered:")
        a("")
        for sub in engagement.subdomains[:100]:
            a(f"- {sub}")
        if len(engagement.subdomains) > 100:
            a(f"- _... and {len(engagement.subdomains) - 100} more_")
        a("")

    # --- OSINT ------------------------------------------------------------
    if engagement.osint:
        a("## OSINT")
        a("")
        a("| Source | Summary |")
        a("| --- | --- |")
        for finding in engagement.osint:
            a(f"| {_esc(finding.category)} | {_esc(finding.value)} |")
        a("")

    if engagement.notes:
        a("## Notes")
        a("")
        a(engagement.notes)
        a("")

    a("---")
    a(f"_{branding.LONG_NAME} v{branding.VERSION} · {branding.ENGINE_CREDIT}._")
    a("")
    return "\n".join(lines)
