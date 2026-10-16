"""Normalised data model for a Sn1per engagement.

The collector turns the raw Sn1per loot directory (nmap XML, sc0pe vuln
files, OSINT text dumps, ...) into these plain dataclasses. Renderers only
ever see this model, never raw files, which keeps parsing and presentation
cleanly separated and makes new output formats cheap to add.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

# Canonical severity ordering, most severe first. Everything else in Jarvis
# (sorting, scoring, colours) keys off this single source of truth.
SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]

# Risk weights mirror Sn1per's own sc0pe scoring so Jarvis numbers line up
# with what the engine already reports.
SEVERITY_WEIGHTS = {"critical": 5, "high": 4, "medium": 3, "low": 2, "info": 1}


@dataclass
class Port:
    number: int
    protocol: str = "tcp"
    state: str = "open"
    service: str = ""
    product: str = ""
    version: str = ""

    @property
    def service_banner(self) -> str:
        parts = [self.product, self.version]
        banner = " ".join(p for p in parts if p).strip()
        return banner or self.service


@dataclass
class Vulnerability:
    severity: str  # normalised to one of SEVERITY_ORDER
    name: str
    location: str = ""  # host or URL the finding applies to
    evidence: str = ""
    source: str = "sc0pe"  # which tool/parser produced it
    remediation: str = ""  # advisory guidance, filled in during collection

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHTS.get(self.severity, 0)


@dataclass
class Host:
    target: str
    ip: str = ""
    status: str = "up"
    os: str = ""
    mac: str = ""
    ports: list[Port] = field(default_factory=list)
    web_urls: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)

    @property
    def open_ports(self) -> list[Port]:
        return [p for p in self.ports if p.state == "open"]


@dataclass
class OsintFinding:
    category: str
    value: str


@dataclass
class Engagement:
    """Top-level container for everything that goes into one report."""

    name: str
    loot_root: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )
    hosts: list[Host] = field(default_factory=list)
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    osint: list[OsintFinding] = field(default_factory=list)
    subdomains: list[str] = field(default_factory=list)
    notes: str = ""

    # --- Derived metrics --------------------------------------------------
    def severity_counts(self) -> dict[str, int]:
        counts = {s: 0 for s in SEVERITY_ORDER}
        for v in self.vulnerabilities:
            if v.severity in counts:
                counts[v.severity] += 1
        return counts

    @property
    def risk_score(self) -> int:
        return sum(v.weight for v in self.vulnerabilities)

    @property
    def risk_rating(self) -> str:
        """Human label derived from the highest-severity finding present."""
        counts = self.severity_counts()
        if counts["critical"]:
            return "Critical"
        if counts["high"]:
            return "High"
        if counts["medium"]:
            return "Medium"
        if counts["low"]:
            return "Low"
        if counts["info"]:
            return "Informational"
        return "Clean"

    @property
    def total_open_ports(self) -> int:
        return sum(len(h.open_ports) for h in self.hosts)

    @property
    def most_exposed_host(self) -> Host | None:
        """Host carrying the most findings (ties broken by open-port count)."""
        if not self.hosts:
            return None
        counts: dict[str, int] = {}
        for v in self.vulnerabilities:
            loc = v.location.lower()
            for h in self.hosts:
                if (h.ip and h.ip in loc) or (h.target and h.target.lower() in loc):
                    key = h.ip or h.target
                    counts[key] = counts.get(key, 0) + 1
        if not counts:
            return max(self.hosts, key=lambda h: len(h.open_ports))
        top_key = max(counts, key=lambda k: counts[k])
        for h in self.hosts:
            if (h.ip or h.target) == top_key:
                return h
        return None

    def narrative_summary(self) -> str:
        """A short, deterministic prose summary for the executive section."""
        counts = self.severity_counts()
        n_hosts = len(self.hosts)
        sentences = [
            f"This engagement covered {n_hosts} live host"
            f"{'s' if n_hosts != 1 else ''} exposing {self.total_open_ports} "
            f"open port{'s' if self.total_open_ports != 1 else ''}."
        ]
        if self.vulnerabilities:
            breakdown = ", ".join(
                f"{counts[s]} {s}" for s in SEVERITY_ORDER if counts[s]
            )
            sentences.append(
                f"Jarvis recorded {len(self.vulnerabilities)} finding"
                f"{'s' if len(self.vulnerabilities) != 1 else ''} ({breakdown})."
            )
            urgent = counts["critical"] + counts["high"]
            if urgent:
                sentences.append(
                    f"{urgent} finding{'s' if urgent != 1 else ''} rated high or "
                    "critical require prompt attention."
                )
            host = self.most_exposed_host
            if host:
                sentences.append(
                    f"The most exposed host is {host.target or host.ip}."
                )
        else:
            sentences.append("No vulnerabilities were recorded in the loot.")
        return " ".join(sentences)

    def vulnerabilities_sorted(self) -> list[Vulnerability]:
        rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
        return sorted(
            self.vulnerabilities,
            key=lambda v: (rank.get(v.severity, len(SEVERITY_ORDER)), v.name.lower()),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["severity_counts"] = self.severity_counts()
        data["risk_score"] = self.risk_score
        data["risk_rating"] = self.risk_rating
        data["total_hosts"] = len(self.hosts)
        data["total_open_ports"] = self.total_open_ports
        data["total_vulnerabilities"] = len(self.vulnerabilities)
        return data
