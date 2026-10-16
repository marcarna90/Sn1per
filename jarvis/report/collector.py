"""Collect a Sn1per loot directory into a normalised :class:`Engagement`.

Parsing is defensive by design: Sn1per loot is assembled by dozens of bash
modules and any individual file may be missing, empty or half-written when a
scan is interrupted. Every parser here tolerates that and simply contributes
whatever it can, so a partial scan still yields a useful report.
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from jarvis.report.importers import collect_extra_vulnerabilities
from jarvis.report.model import Engagement, Host, OsintFinding, Port, Vulnerability
from jarvis.report.severity import normalize

# Aggregate/bookkeeping files inside vulnerabilities/ that are NOT individual
# findings and must be skipped so we don't double-count or parse noise.
_VULN_SKIP = re.compile(
    r"(all-vulnerabilities-sorted|vulnerability-report|vulnerability-risk|"
    r"_vulns_total|vuln_score_total)",
    re.IGNORECASE,
)

# Keep the report readable: cap obviously unbounded lists.
_MAX_WEB_URLS = 200
_MAX_SUBDOMAINS = 1000
_MAX_EVIDENCE = 500


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _nonempty_lines(path: Path) -> list[str]:
    return [ln.strip() for ln in _read_text(path).splitlines() if ln.strip()]


# --------------------------------------------------------------------------
# nmap
# --------------------------------------------------------------------------
def _parse_nmap_xml(path: Path, hosts: dict[str, Host]) -> None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return

    for host_el in root.findall("host"):
        status_el = host_el.find("status")
        status = status_el.get("state", "up") if status_el is not None else "up"

        ip = ""
        mac = ""
        for addr in host_el.findall("address"):
            kind = addr.get("addrtype", "")
            if kind in ("ipv4", "ipv6") and not ip:
                ip = addr.get("addr", "")
            elif kind == "mac":
                mac = addr.get("addr", "")
                vendor = addr.get("vendor", "")
                if vendor:
                    mac = f"{mac} ({vendor})"

        hostname = ""
        hostnames_el = host_el.find("hostnames")
        if hostnames_el is not None:
            hn = hostnames_el.find("hostname")
            if hn is not None:
                hostname = hn.get("name", "")

        os_name = ""
        os_el = host_el.find("os")
        if os_el is not None:
            match = os_el.find("osmatch")
            if match is not None:
                os_name = match.get("name", "")

        key = ip or hostname or f"host-{len(hosts)}"
        host = hosts.get(key)
        if host is None:
            host = Host(target=hostname or ip or key, ip=ip, status=status)
            hosts[key] = host
        if hostname and (not host.target or host.target == host.ip):
            host.target = hostname
        if os_name and not host.os:
            host.os = os_name
        if mac and not host.mac:
            host.mac = mac

        ports_el = host_el.find("ports")
        if ports_el is None:
            continue
        existing = {(p.number, p.protocol) for p in host.ports}
        for port_el in ports_el.findall("port"):
            state_el = port_el.find("state")
            state = state_el.get("state", "") if state_el is not None else ""
            if state != "open":
                continue
            try:
                number = int(port_el.get("portid", "0"))
            except ValueError:
                continue
            proto = port_el.get("protocol", "tcp")
            if (number, proto) in existing:
                continue
            svc_el = port_el.find("service")
            service = product = version = ""
            if svc_el is not None:
                service = svc_el.get("name", "")
                product = svc_el.get("product", "")
                version = svc_el.get("version", "")
            host.ports.append(
                Port(
                    number=number,
                    protocol=proto,
                    state="open",
                    service=service,
                    product=product,
                    version=version,
                )
            )
            existing.add((number, proto))


def _parse_ports_txt(root: Path, hosts: dict[str, Host]) -> None:
    """Fallback when no nmap XML exists: ports-<target>.txt has one port/line."""
    nmap_dir = root / "nmap"
    if not nmap_dir.is_dir():
        return
    for path in sorted(nmap_dir.glob("ports-*.txt")):
        m = re.match(r"ports-(.+)\.txt$", path.name)
        if not m:
            continue
        target = m.group(1)
        if any(h.target == target or h.ip == target for h in hosts.values()):
            continue
        host = Host(target=target, ip=target if _looks_like_ip(target) else "")
        for line in _nonempty_lines(path):
            try:
                host.ports.append(Port(number=int(line.split()[0])))
            except (ValueError, IndexError):
                continue
        if host.ports:
            hosts[target] = host


def _looks_like_ip(value: str) -> bool:
    return bool(re.match(r"^\d{1,3}(\.\d{1,3}){3}$", value))


def _attach_os_and_web(root: Path, hosts: dict[str, Host]) -> None:
    nmap_dir = root / "nmap"
    web_dir = root / "web"
    by_name = {h.target: h for h in hosts.values()}
    by_name.update({h.ip: h for h in hosts.values() if h.ip})
    for host in hosts.values():
        keys = {host.target, host.ip} - {""}
        for key in keys:
            if nmap_dir.is_dir() and not host.os:
                os_file = nmap_dir / f"osfingerprint-{key}.txt"
                text = _read_text(os_file).strip()
                if text:
                    host.os = text
            if web_dir.is_dir() and not host.web_urls:
                for pattern in (f"dirsearch-{key}.txt", f"spider-{key}.txt"):
                    wf = web_dir / pattern
                    urls = _nonempty_lines(wf)
                    if urls:
                        host.web_urls = urls[:_MAX_WEB_URLS]
                        break


# --------------------------------------------------------------------------
# vulnerabilities (sc0pe)
# --------------------------------------------------------------------------
def _parse_vulns(root: Path) -> list[Vulnerability]:
    vulns: list[Vulnerability] = []
    for path in sorted(root.rglob("sc0pe-*.txt")):
        if _VULN_SKIP.search(path.name):
            continue
        for line in _nonempty_lines(path):
            parts = [p.strip() for p in line.split(",", 3)]
            if not parts or not parts[0]:
                continue
            severity = normalize(parts[0])
            name = parts[1] if len(parts) > 1 else "Unnamed finding"
            location = parts[2] if len(parts) > 2 else ""
            evidence = parts[3] if len(parts) > 3 else ""
            # Sn1per modules replace '<' with the non-standard '&lh;' entity
            # before writing loot; restore it for clean display.
            evidence = evidence.replace("&lh;", "<")[:_MAX_EVIDENCE]
            vulns.append(
                Vulnerability(
                    severity=severity,
                    name=name,
                    location=location,
                    evidence=evidence,
                )
            )
    return vulns


def _dedupe_vulns(vulns: list[Vulnerability]) -> list[Vulnerability]:
    """Drop duplicate findings across all sources (sc0pe + importers)."""
    seen: set[tuple[str, str, str]] = set()
    out: list[Vulnerability] = []
    for v in vulns:
        key = (v.severity, v.name.lower().strip(), v.location.lower().strip())
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


# --------------------------------------------------------------------------
# subdomains & OSINT
# --------------------------------------------------------------------------
def _parse_subdomains(root: Path) -> list[str]:
    domains_dir = root / "domains"
    if not domains_dir.is_dir():
        return []
    candidates = [
        "domains-all-sorted.txt",
        "targets-all-sorted.txt",
        "targets.txt",
    ]
    found: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        for line in _nonempty_lines(domains_dir / name):
            if line not in seen:
                seen.add(line)
                found.append(line)
    # Also fold in raw subdomain-enumeration output when present.
    for pattern in ("subfinder-*.txt", "amass-*.txt", "httpx-*.txt", "subdomains-*.txt"):
        for path in sorted(domains_dir.glob(pattern)):
            for line in _nonempty_lines(path):
                token = line.split()[0] if line.split() else line
                if token and token not in seen:
                    seen.add(token)
                    found.append(token)
    return found[:_MAX_SUBDOMAINS]


def _parse_osint(root: Path) -> list[OsintFinding]:
    osint_dir = root / "osint"
    if not osint_dir.is_dir():
        return []
    findings: list[OsintFinding] = []
    for path in sorted(osint_dir.glob("*")):
        if not path.is_file():
            continue
        lines = _nonempty_lines(path)
        if not lines:
            continue
        category = path.stem.replace("-", " ").replace("_", " ").strip()
        summary = f"{len(lines)} item(s)"
        preview = lines[0]
        if len(preview) > 120:
            preview = preview[:117] + "..."
        findings.append(
            OsintFinding(category=category, value=f"{summary} — e.g. {preview}")
        )
    return findings


def _read_notes(root: Path) -> str:
    for candidate in (root / "notes" / "notes.txt", root / "notes.txt"):
        text = _read_text(candidate).strip()
        if text:
            return text
    return ""


# --------------------------------------------------------------------------
# public entry point
# --------------------------------------------------------------------------
def collect(loot_root: str | os.PathLike, name: str | None = None) -> Engagement:
    """Build an :class:`Engagement` from a Sn1per loot directory."""
    root = Path(loot_root).expanduser().resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Loot directory not found: {root}")

    engagement = Engagement(name=name or root.name, loot_root=str(root))

    hosts: dict[str, Host] = {}
    for xml_path in sorted(root.rglob("nmap-*.xml")):
        _parse_nmap_xml(xml_path, hosts)
    _parse_ports_txt(root, hosts)
    _attach_os_and_web(root, hosts)

    engagement.hosts = sorted(hosts.values(), key=lambda h: (h.ip or h.target))
    # Combine Sn1per's own sc0pe findings with native third-party scanner
    # output (nuclei / Nessus / OpenVAS), then dedupe across all sources.
    engagement.vulnerabilities = _dedupe_vulns(
        _parse_vulns(root) + collect_extra_vulnerabilities(root)
    )
    engagement.subdomains = _parse_subdomains(root)
    engagement.osint = _parse_osint(root)
    engagement.notes = _read_notes(root)
    return engagement
