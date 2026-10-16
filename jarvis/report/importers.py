"""Extra finding importers for third-party scanners Sn1per integrates with.

Sn1per already shells out to nuclei, Nessus and OpenVAS/GVM in its various
modes, but the Community edition only ever folds a subset of that into its
sc0pe text files. These importers read the native output of those tools when
it is present in the loot directory, so the report reflects everything that
ran — not just what sc0pe captured.

Every importer is defensive: unreadable, empty or unexpectedly-shaped files
contribute nothing rather than raising.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from jarvis.report.model import Vulnerability
from jarvis.report.severity import normalize

_MAX_EVIDENCE = 500

# Nessus numeric severity (0..4) -> canonical label.
_NESSUS_SEVERITY = {0: "info", 1: "low", 2: "medium", 3: "high", 4: "critical"}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


# --------------------------------------------------------------------------
# nuclei  (jsonl / json  -- `nuclei -json` / `-jsonl`)
# --------------------------------------------------------------------------
def from_nuclei(root: Path) -> list[Vulnerability]:
    vulns: list[Vulnerability] = []
    candidates: list[Path] = []
    for sub in ("vulnerabilities", "output", "web", "."):
        d = root / sub
        if d.is_dir():
            candidates += list(d.glob("*nuclei*.json"))
            candidates += list(d.glob("*nuclei*.jsonl"))
    for path in sorted(set(candidates)):
        for line in _read_text(path).splitlines():
            line = line.strip()
            if not line or not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            info = obj.get("info") or {}
            severity = normalize(str(info.get("severity", "info")))
            name = str(
                info.get("name") or obj.get("template-id") or obj.get("templateID") or "nuclei finding"
            )
            location = str(
                obj.get("matched-at") or obj.get("matched_at") or obj.get("host") or ""
            )
            evidence = str(obj.get("extracted-results") or info.get("description") or "")
            vulns.append(
                Vulnerability(
                    severity=severity,
                    name=name,
                    location=location,
                    evidence=evidence[:_MAX_EVIDENCE],
                    source="nuclei",
                )
            )
    return vulns


# --------------------------------------------------------------------------
# Nessus  (*.nessus -- Tenable XML export)
# --------------------------------------------------------------------------
def from_nessus(root: Path) -> list[Vulnerability]:
    vulns: list[Vulnerability] = []
    for path in sorted(root.rglob("*.nessus")):
        try:
            tree = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for host in tree.iter("ReportHost"):
            target = host.get("name", "")
            for item in host.findall("ReportItem"):
                try:
                    sev_num = int(item.get("severity", "0"))
                except ValueError:
                    sev_num = 0
                severity = _NESSUS_SEVERITY.get(sev_num, "info")
                name = item.get("pluginName", "Nessus finding")
                port = item.get("port", "")
                location = f"{target}:{port}" if port and port != "0" else target
                synopsis = item.findtext("synopsis", default="").strip()
                vulns.append(
                    Vulnerability(
                        severity=severity,
                        name=name,
                        location=location,
                        evidence=synopsis[:_MAX_EVIDENCE],
                        source="nessus",
                    )
                )
    return vulns


# --------------------------------------------------------------------------
# OpenVAS / GVM  (XML report with <result><threat>..)
# --------------------------------------------------------------------------
_GVM_THREAT = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "log": "info",
    "alarm": "medium",
}


def _looks_like_gvm(path: Path) -> bool:
    head = _read_text(path)[:4000].lower()
    return ("<result" in head and "<threat" in head) or "get_reports_response" in head


def from_openvas(root: Path) -> list[Vulnerability]:
    vulns: list[Vulnerability] = []
    for path in sorted(root.rglob("*.xml")):
        if re.match(r"nmap-", path.name):  # skip nmap scans
            continue
        if not _looks_like_gvm(path):
            continue
        try:
            tree = ET.parse(path).getroot()
        except (ET.ParseError, OSError):
            continue
        for result in tree.iter("result"):
            threat = (result.findtext("threat") or "").strip().lower()
            severity = _GVM_THREAT.get(threat, normalize(threat))
            nvt = result.find("nvt")
            name = (nvt.findtext("name") if nvt is not None else None) or "OpenVAS finding"
            host = (result.findtext("host") or "").strip()
            port = (result.findtext("port") or "").strip()
            location = f"{host}:{port}" if host and port else host
            desc = (result.findtext("description") or "").strip()
            vulns.append(
                Vulnerability(
                    severity=severity,
                    name=name,
                    location=location,
                    evidence=desc[:_MAX_EVIDENCE],
                    source="openvas",
                )
            )
    return vulns


def collect_extra_vulnerabilities(root: Path) -> list[Vulnerability]:
    """Run every third-party importer and return the combined findings."""
    found: list[Vulnerability] = []
    for importer in (from_nuclei, from_nessus, from_openvas):
        try:
            found += importer(root)
        except Exception:  # pragma: no cover - importer must never be fatal
            continue
    return found
