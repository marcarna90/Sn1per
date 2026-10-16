"""Build an :class:`AttackSurface` from a report-engine :class:`Engagement`.

Everything here is offline: it derives the asset inventory and the EASM
exposure set from loot Sn1per already collected. Live enrichment (DNS, TLS,
typosquat resolution) is layered on separately so the core stays testable
without a network.
"""

from __future__ import annotations

import re

from jarvis.asm.model import (
    Asset,
    AssetKind,
    AttackSurface,
    Exposure,
    category_default_severity,
)
from jarvis.report import remediation
from jarvis.report.model import Engagement

# Port -> exposure classification.
DB_PORTS = {1433, 1521, 3050, 3306, 5432, 5984, 6379, 9200, 11211, 27017}
REMOTE_PORTS = {22, 23, 512, 513, 514, 3389, 5900, 5901, 5902}

_ADMIN_TOKENS = (
    "/admin", "/administrator", "/login", "/manage", "/manager", "/phpmyadmin",
    "/wp-admin", "/cpanel", "/webadmin", "/console", "/dashboard",
)
_SENSITIVE_TOKENS = (
    "/.git", "/.env", ".sql", ".bak", "backup", ".zip", ".tar", "dump",
    "id_rsa", ".htpasswd", ".dockercfg", "/.svn",
)

# Vulnerability name/location keyword -> exposure category (ordered, first win).
_VULN_RULES: list[tuple[tuple[str, ...], str]] = [
    (("takeover",), "subdomain_takeover"),
    (("open relay", "spf", "dmarc", "dkim", "spoof"), "missing_email_security"),
    (("heartbleed", "ssl", "tls", "cipher", "certificate", " cert"), "weak_tls"),
    (("security header", "content-security", "x-frame", "hsts", "clickjack",
      "directory listing", "cors"), "misconfiguration"),
    (("default credential", "default password", "weak password",
      "default account"), "default_credentials"),
    ((".git", ".env", "backup", "exposed", "robots.txt"), "exposed_sensitive_file"),
    (("sql injection", "sqli", "rce", "remote code", "command execution",
      "deserial", "lfi", "rfi", "ssrf", "xxe", "traversal", "auth bypass",
      "xss", "cve-", "exploit"), "vulnerable_service"),
    (("version", "banner", "discloses", "disclosure", "tech-detect",
      "server:"), "information_disclosure"),
]


def _classify_vuln(name: str, location: str) -> str:
    hay = f"{name} {location}".lower()
    for keywords, category in _VULN_RULES:
        if any(k in hay for k in keywords):
            return category
    return "other"


def _is_subdomain(host: str) -> bool:
    # Heuristic: more than two dot-separated labels => subdomain. Good enough
    # for reporting; ccTLD edge cases (co.uk) only mislabel, never drop.
    return host.count(".") >= 2


def _dedupe_exposures(exposures: list[Exposure]) -> list[Exposure]:
    seen: set[tuple[str, str, str]] = set()
    out: list[Exposure] = []
    for e in exposures:
        key = (e.category, e.asset.lower(), e.title.lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def build_attack_surface(engagement: Engagement, client: str = "") -> AttackSurface:
    surface = AttackSurface(
        name=engagement.name,
        client=client,
        generated_at=engagement.generated_at,
    )
    ts = engagement.generated_at
    assets: list[Asset] = []
    exposures: list[Exposure] = []
    tech_seen: set[str] = set()

    # --- subdomains / domains --------------------------------------------
    for sub in engagement.subdomains:
        kind = AssetKind.SUBDOMAIN.value if _is_subdomain(sub) else AssetKind.DOMAIN.value
        assets.append(Asset(kind=kind, value=sub, source="dns", first_seen=ts, last_seen=ts))

    # --- hosts, services, technologies -----------------------------------
    for host in engagement.hosts:
        host_id = host.target or host.ip
        if host.ip:
            assets.append(
                Asset(
                    kind=AssetKind.IP.value,
                    value=host.ip,
                    parent=host.target,
                    source="nmap",
                    attributes={"os": host.os} if host.os else {},
                    first_seen=ts,
                    last_seen=ts,
                )
            )
        for port in host.open_ports:
            svc_value = f"{host_id}:{port.number}/{port.protocol}"
            assets.append(
                Asset(
                    kind=AssetKind.SERVICE.value,
                    value=svc_value,
                    parent=host_id,
                    source="nmap",
                    attributes={
                        "port": port.number,
                        "service": port.service,
                        "banner": port.service_banner,
                    },
                    first_seen=ts,
                    last_seen=ts,
                )
            )
            if port.service_banner and port.service_banner.lower() not in tech_seen:
                tech_seen.add(port.service_banner.lower())
                assets.append(
                    Asset(
                        kind=AssetKind.TECHNOLOGY.value,
                        value=port.service_banner,
                        parent=host_id,
                        source="nmap",
                        first_seen=ts,
                        last_seen=ts,
                    )
                )

            # service-derived exposures
            if port.number in DB_PORTS:
                exposures.append(
                    Exposure(
                        category="open_database",
                        title=f"{port.service or 'Database'} exposed on port {port.number}",
                        severity=category_default_severity("open_database"),
                        asset=svc_value,
                        detail=f"{port.service_banner or port.service} reachable at {svc_value}",
                        remediation=remediation.suggest(port.service or "database", "", "critical"),
                        source="asm",
                    )
                )
            elif port.number in REMOTE_PORTS:
                exposures.append(
                    Exposure(
                        category="remote_access_exposed",
                        title=f"{port.service or 'Remote access'} exposed on port {port.number}",
                        severity=category_default_severity("remote_access_exposed"),
                        asset=svc_value,
                        detail=f"{port.service_banner or port.service} reachable at {svc_value}",
                        remediation="Restrict access to a VPN/bastion or allow-listed IPs; enforce MFA.",
                        source="asm",
                    )
                )

        # web-path-derived exposures
        for url in host.web_urls:
            low = url.lower()
            if any(tok in low for tok in _SENSITIVE_TOKENS):
                exposures.append(
                    Exposure(
                        category="exposed_sensitive_file",
                        title="Sensitive path reachable",
                        severity=category_default_severity("exposed_sensitive_file"),
                        asset=url,
                        detail=url,
                        remediation="Remove the resource from the web root or restrict access; rotate any leaked secrets.",
                        source="asm",
                    )
                )
            elif any(tok in low for tok in _ADMIN_TOKENS):
                exposures.append(
                    Exposure(
                        category="exposed_admin_interface",
                        title="Administrative interface reachable",
                        severity=category_default_severity("exposed_admin_interface"),
                        asset=url,
                        detail=url,
                        remediation="Restrict the admin UI to trusted networks/VPN and enforce strong auth + MFA.",
                        source="asm",
                    )
                )

    # --- email domains (from OSINT emails) --------------------------------
    email_domains: set[str] = set()
    for finding in engagement.osint:
        for match in re.findall(r"[\w.+-]+@([\w.-]+\.[A-Za-z]{2,})", finding.value):
            email_domains.add(match.lower())
    for dom in sorted(email_domains):
        assets.append(
            Asset(kind=AssetKind.EMAIL_DOMAIN.value, value=dom, source="osint",
                  first_seen=ts, last_seen=ts)
        )

    # --- map existing findings into exposure categories -------------------
    for v in engagement.vulnerabilities:
        category = _classify_vuln(v.name, v.location)
        exposures.append(
            Exposure(
                category=category,
                title=v.name,
                severity=v.severity,
                asset=v.location,
                detail=v.evidence,
                remediation=v.remediation or remediation.suggest(v.name, v.location, v.severity),
                source=v.source,
            )
        )

    surface.assets = assets
    surface.exposures = _dedupe_exposures(exposures)
    return surface
