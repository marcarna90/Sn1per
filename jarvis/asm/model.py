"""Attack Surface Management (ASM) data model.

This layer sits above the report engine's :class:`Engagement`. Where the
report model answers "what did we find on these hosts", the ASM model answers
the EASM questions a client cares about: "what of mine is exposed to the
internet, how bad is my exposure, and is it getting better or worse?"

Three concepts:

* **Asset** - a discovered, classified piece of the attack surface
  (domain, subdomain, IP, service, certificate, technology, email domain).
* **Exposure** - a risk observation mapped to an EASM *category* (an exposed
  admin panel, an open database, a weak certificate, ...), not just a CVSS row.
* **Posture** - an A-F grade (global and per-category) derived from exposures,
  so a client sees a security-rating-style verdict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from jarvis.report.model import SEVERITY_ORDER, SEVERITY_WEIGHTS


class AssetKind(str, Enum):
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP = "ip"
    SERVICE = "service"
    CERTIFICATE = "certificate"
    TECHNOLOGY = "technology"
    EMAIL_DOMAIN = "email_domain"


# EASM exposure categories: key -> (label, default severity, one-line meaning).
EXPOSURE_CATEGORIES: dict[str, tuple[str, str, str]] = {
    "exposed_admin_interface": (
        "Exposed admin interface", "high",
        "Administrative or management UI reachable from the internet.",
    ),
    "open_database": (
        "Internet-exposed database", "critical",
        "A database service is reachable from untrusted networks.",
    ),
    "remote_access_exposed": (
        "Exposed remote-access service", "medium",
        "Remote-access service (RDP/SSH/VNC/Telnet) reachable from the internet.",
    ),
    "exposed_sensitive_file": (
        "Exposed sensitive file", "high",
        "A sensitive file or path (.git, .env, backup, dump) is reachable.",
    ),
    "vulnerable_service": (
        "Vulnerable service", "high",
        "A service with a known vulnerability or exploitable weakness.",
    ),
    "weak_tls": (
        "Weak or expired TLS", "medium",
        "Expired/invalid certificate or weak TLS protocol/cipher.",
    ),
    "missing_email_security": (
        "Missing email authentication", "medium",
        "SPF, DKIM or DMARC is missing or weak, enabling spoofing.",
    ),
    "subdomain_takeover": (
        "Subdomain takeover risk", "high",
        "A subdomain points to an unclaimed third-party resource.",
    ),
    "information_disclosure": (
        "Information disclosure", "low",
        "Software versions/banners or metadata leak useful detail.",
    ),
    "misconfiguration": (
        "Security misconfiguration", "medium",
        "Missing security headers, directory listing, or unsafe defaults.",
    ),
    "default_credentials": (
        "Default or weak credentials", "high",
        "Default/guessable credentials or an unauthenticated admin surface.",
    ),
    "typosquat_domain": (
        "Look-alike / typosquat domain", "medium",
        "A registered domain closely resembles the client's brand.",
    ),
    "other": (
        "Other exposure", "info",
        "An exposure that does not fit a more specific category.",
    ),
}


def category_label(key: str) -> str:
    return EXPOSURE_CATEGORIES.get(key, EXPOSURE_CATEGORIES["other"])[0]


def category_default_severity(key: str) -> str:
    return EXPOSURE_CATEGORIES.get(key, EXPOSURE_CATEGORIES["other"])[1]


@dataclass
class Asset:
    kind: str  # one of AssetKind values
    value: str
    parent: str = ""  # e.g. the host an SERVICE/CERTIFICATE belongs to
    source: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    first_seen: str = ""
    last_seen: str = ""

    @property
    def identity(self) -> tuple[str, str]:
        return (self.kind, self.value.lower())


@dataclass
class Exposure:
    category: str  # key in EXPOSURE_CATEGORIES
    title: str
    severity: str
    asset: str = ""  # the asset value this exposure applies to
    detail: str = ""
    remediation: str = ""
    source: str = ""

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHTS.get(self.severity, 0)


# Grade thresholds (score out of 100) -> (letter, label).
_GRADE_BANDS = [
    (90, "A", "Excellent"),
    (80, "B", "Good"),
    (70, "C", "Fair"),
    (60, "D", "Poor"),
    (0, "F", "Critical"),
]

# Penalty per finding severity, subtracted from a starting score of 100.
_PENALTY = {"critical": 25, "high": 12, "medium": 5, "low": 2, "info": 0.5}


def score_to_grade(score: float) -> tuple[str, str]:
    for threshold, letter, label in _GRADE_BANDS:
        if score >= threshold:
            return letter, label
    return "F", "Critical"


def grade_from_exposures(exposures: list[Exposure]) -> tuple[float, str, str]:
    """Return (score 0-100, letter, label) for a set of exposures."""
    score = 100.0
    for e in exposures:
        score -= _PENALTY.get(e.severity, 0)
    score = max(0.0, round(score, 1))
    letter, label = score_to_grade(score)
    return score, letter, label


@dataclass
class AttackSurface:
    name: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )
    client: str = ""
    assets: list[Asset] = field(default_factory=list)
    exposures: list[Exposure] = field(default_factory=list)

    # --- asset views ------------------------------------------------------
    def assets_by_kind(self) -> dict[str, list[Asset]]:
        out: dict[str, list[Asset]] = {k.value: [] for k in AssetKind}
        for a in self.assets:
            out.setdefault(a.kind, []).append(a)
        return out

    def asset_counts(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.assets_by_kind().items()}

    # --- exposure views ---------------------------------------------------
    def exposures_by_category(self) -> dict[str, list[Exposure]]:
        out: dict[str, list[Exposure]] = {}
        for e in self.exposures:
            out.setdefault(e.category, []).append(e)
        return out

    def severity_counts(self) -> dict[str, int]:
        counts = {s: 0 for s in SEVERITY_ORDER}
        for e in self.exposures:
            if e.severity in counts:
                counts[e.severity] += 1
        return counts

    def exposures_sorted(self) -> list[Exposure]:
        rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
        return sorted(
            self.exposures,
            key=lambda e: (rank.get(e.severity, 99), e.category, e.title.lower()),
        )

    # --- posture ----------------------------------------------------------
    def posture(self) -> dict[str, Any]:
        score, letter, label = grade_from_exposures(self.exposures)
        per_category: dict[str, Any] = {}
        for cat, items in self.exposures_by_category().items():
            c_score, c_letter, c_label = grade_from_exposures(items)
            per_category[cat] = {
                "label": category_label(cat),
                "count": len(items),
                "score": c_score,
                "grade": c_letter,
                "rating": c_label,
            }
        return {
            "score": score,
            "grade": letter,
            "rating": label,
            "per_category": per_category,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "client": self.client,
            "generated_at": self.generated_at,
            "asset_counts": self.asset_counts(),
            "total_assets": len(self.assets),
            "total_exposures": len(self.exposures),
            "severity_counts": self.severity_counts(),
            "posture": self.posture(),
            "assets": [a.__dict__ for a in self.assets],
            "exposures": [e.__dict__ for e in self.exposures],
        }
