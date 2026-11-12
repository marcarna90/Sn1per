"""Domain enumerations shared by every layer (stored as readable text, ADR 0003)."""

import enum
from typing import Self


class Role(enum.StrEnum):
    """RBAC roles, ordered by privilege: viewer < analyst < admin."""

    viewer = "viewer"
    analyst = "analyst"
    admin = "admin"

    @property
    def rank(self) -> int:
        return {"viewer": 1, "analyst": 2, "admin": 3}[self.value]

    def at_least(self, minimum: Self) -> bool:
        return self.rank >= minimum.rank


class ScopeKind(enum.StrEnum):
    domain = "domain"
    ip = "ip"
    cidr = "cidr"


class NetworkClass(enum.StrEnum):
    """Whether an authorised range is on the public Internet or a private network."""

    external = "external"
    internal = "internal"


class ScanStatus(enum.StrEnum):
    pending = "pending"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {ScanStatus.succeeded, ScanStatus.failed, ScanStatus.cancelled}


class Severity(enum.StrEnum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FindingCategory(enum.StrEnum):
    asset = "asset"
    dns_record = "dns_record"
    open_port = "open_port"
    service = "service"
    vulnerability = "vulnerability"
    misconfiguration = "misconfiguration"
    info = "info"


class AuditOutcome(enum.StrEnum):
    success = "success"
    denied = "denied"
    failure = "failure"
