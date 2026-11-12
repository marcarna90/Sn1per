"""Building scope rules from administrator input.

Validation here is the only way a rule is created; the engine still re-derives the
network class from the addresses themselves, so a row edited out-of-band cannot
widen what is authorised.
"""

from ipaddress import ip_address, ip_network

from neo_orchestro.core.enums import NetworkClass, ScopeKind
from neo_orchestro.scope.network import (
    IPNetwork,
    classify_ip,
    normalise_ip,
    overlaps_hard_denied,
)
from neo_orchestro.scope.parsing import format_ip, parse_target
from neo_orchestro.scope.types import (
    HARD_DENIED,
    InvalidScopeEntryError,
    InvalidTargetError,
    IpClass,
    ScopeLimits,
    ScopeRule,
)


def _network_class(ip_class: IpClass) -> NetworkClass:
    return NetworkClass.internal if ip_class is IpClass.private else NetworkClass.external


def build_rule(
    kind: ScopeKind,
    raw: str,
    *,
    include_subdomains: bool = False,
    limits: ScopeLimits | None = None,
    rule_id: str = "",
) -> ScopeRule:
    """Validate and normalise a scope entry, deriving its network class.

    Raises:
        InvalidScopeEntryError: malformed, too broad, mixes public/private space, or touches
            a never-scannable range (loopback, link-local, multicast, metadata, ...).
    """
    limits = limits or ScopeLimits()
    if include_subdomains and kind is not ScopeKind.domain:
        raise InvalidScopeEntryError("include_subdomains is only valid for domain entries")

    if kind is ScopeKind.domain:
        return _domain_rule(raw, include_subdomains, rule_id)
    if kind is ScopeKind.ip:
        return _ip_rule(raw, rule_id)
    return _cidr_rule(raw, limits, rule_id)


def _domain_rule(raw: str, include_subdomains: bool, rule_id: str) -> ScopeRule:
    try:
        parsed = parse_target(raw)
    except InvalidTargetError as exc:
        raise InvalidScopeEntryError(f"invalid domain: {exc}") from exc
    if parsed.kind is not ScopeKind.domain:
        raise InvalidScopeEntryError("expected a domain name, got an IP address")
    return ScopeRule(
        rule_id, ScopeKind.domain, parsed.value, include_subdomains, NetworkClass.external
    )


def _ip_rule(raw: str, rule_id: str) -> ScopeRule:
    try:
        parsed = parse_target(raw)
    except InvalidTargetError as exc:
        raise InvalidScopeEntryError(f"invalid IP address: {exc}") from exc
    if parsed.kind is not ScopeKind.ip:
        raise InvalidScopeEntryError("expected an IP address, got a domain name")
    ip = normalise_ip(ip_address(parsed.value))
    ip_class = classify_ip(ip)
    if ip_class in HARD_DENIED:
        raise InvalidScopeEntryError(f"{ip} is in a blocked address class ({ip_class.value})")
    return ScopeRule(rule_id, ScopeKind.ip, format_ip(ip), False, _network_class(ip_class))


def _cidr_rule(raw: str, limits: ScopeLimits, rule_id: str) -> ScopeRule:
    if "/" not in raw:
        # ip_network() would silently accept a bare address as a /32.
        raise InvalidScopeEntryError(
            "CIDR needs a prefix length (e.g. 10.0.0.0/24); use an IP entry for a single host"
        )
    try:
        network: IPNetwork = ip_network(raw.strip(" "), strict=True)
    except ValueError as exc:
        message = str(exc)
        if "host bits" in message:
            raise InvalidScopeEntryError("CIDR has host bits set; use the network address") from exc
        raise InvalidScopeEntryError(f"invalid CIDR: {message}") from exc

    minimum = limits.min_prefix_v4 if network.version == 4 else limits.min_prefix_v6
    if network.prefixlen < minimum:
        raise InvalidScopeEntryError(
            f"CIDR is too broad: /{network.prefixlen} is shorter than the allowed /{minimum}"
        )
    if overlaps_hard_denied(network):
        raise InvalidScopeEntryError(
            "CIDR overlaps a blocked address range (loopback, link-local, ...)"
        )

    first = classify_ip(network[0])
    last = classify_ip(network[-1])
    if first is not last:
        raise InvalidScopeEntryError("CIDR mixes public and private address space")
    if first in HARD_DENIED:
        raise InvalidScopeEntryError(f"CIDR is in a blocked address class ({first.value})")
    return ScopeRule(rule_id, ScopeKind.cidr, str(network), False, _network_class(first))
