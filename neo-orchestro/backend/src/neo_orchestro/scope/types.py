"""Value types, errors and enumerations of the scope engine.

Imports only ``core`` — never the database, API or orchestrator (ADR 0002).
"""

import enum
from dataclasses import dataclass, field
from typing import Any

from neo_orchestro.core.enums import NetworkClass, ScopeKind


class DenyReason(enum.StrEnum):
    """Stable machine codes explaining a refusal (stored in audit logs, shown in the UI)."""

    invalid_target = "invalid_target"
    not_in_scope = "not_in_scope"
    blocked_address = "blocked_address"
    internal_not_authorised = "internal_not_authorised"
    unresolvable = "unresolvable"
    resolution_failed = "resolution_failed"
    too_many_addresses = "too_many_addresses"
    scheme_not_allowed = "scheme_not_allowed"
    userinfo_not_allowed = "userinfo_not_allowed"
    too_many_redirects = "too_many_redirects"


class IpClass(enum.StrEnum):
    """What kind of address an IP is, as far as scanning policy is concerned."""

    public = "public"
    private = "private"  # RFC 1918, ULA, CGNAT, documentation: "internal"
    loopback = "loopback"
    link_local = "link_local"
    unspecified = "unspecified"
    multicast = "multicast"
    reserved = "reserved"
    metadata = "metadata"  # cloud instance-metadata endpoints outside link-local


# Never scannable, whatever the scope rules say.
HARD_DENIED = frozenset(
    {
        IpClass.loopback,
        IpClass.link_local,
        IpClass.unspecified,
        IpClass.multicast,
        IpClass.reserved,
        IpClass.metadata,
    }
)


class InvalidTargetError(ValueError):
    """The text is not an acceptable scan target."""


class InvalidScopeEntryError(ValueError):
    """The scope entry cannot be created (malformed, too broad, or dangerous)."""


class ResolutionError(Exception):
    """DNS could not be answered reliably (timeout, SERVFAIL, ...). Callers fail closed."""


class NoSuchDomainError(ResolutionError):
    """The name does not exist or has no A/AAAA records."""


@dataclass(frozen=True, slots=True)
class ParsedTarget:
    kind: ScopeKind  # domain | ip
    value: str  # normalised


@dataclass(frozen=True, slots=True)
class ScopeRule:
    """One authorised range: a domain, an IP, or a CIDR (already normalised)."""

    id: str
    kind: ScopeKind
    value: str
    include_subdomains: bool
    network_class: NetworkClass


@dataclass(frozen=True, slots=True)
class ScopeLimits:
    min_prefix_v4: int = 16
    min_prefix_v6: int = 48
    max_resolved_ips: int = 16


@dataclass(frozen=True, slots=True)
class Decision:
    """Outcome of a scope evaluation.

    ``pinned_ips`` are the *validated* addresses: executors must connect to these,
    not re-resolve the name (anti-rebinding). Empty whenever the decision is a denial.
    """

    allowed: bool
    reason: DenyReason | None = None
    target: str | None = None
    pinned_ips: tuple[str, ...] = ()
    matched_rule_ids: tuple[str, ...] = ()
    details: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason.value if self.reason else None,
            "target": self.target,
            "pinned_ips": list(self.pinned_ips),
            "matched_rule_ids": list(self.matched_rule_ids),
            "details": dict(self.details),
        }
