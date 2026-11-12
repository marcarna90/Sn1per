"""Building scope rules: normalisation, class derivation and hard limits."""

import pytest

from neo_orchestro.core.enums import NetworkClass, ScopeKind
from neo_orchestro.scope import InvalidScopeEntryError, ScopeLimits, build_rule


@pytest.mark.unit
def test_domain_rule_is_normalised_and_external() -> None:
    rule = build_rule(ScopeKind.domain, "Example.COM.", include_subdomains=True)
    assert (rule.kind, rule.value, rule.include_subdomains) == (
        ScopeKind.domain,
        "example.com",
        True,
    )
    assert rule.network_class is NetworkClass.external


@pytest.mark.unit
@pytest.mark.parametrize(
    ("kind", "raw", "value", "net_class"),
    [
        (ScopeKind.ip, "93.184.216.34", "93.184.216.34", NetworkClass.external),
        (ScopeKind.ip, "10.1.2.3", "10.1.2.3", NetworkClass.internal),
        (ScopeKind.ip, "192.168.1.10", "192.168.1.10", NetworkClass.internal),
        (ScopeKind.ip, "2001:4860:4860::8888", "2001:4860:4860::8888", NetworkClass.external),
        (ScopeKind.cidr, "93.184.216.0/24", "93.184.216.0/24", NetworkClass.external),
        (ScopeKind.cidr, "10.0.0.0/16", "10.0.0.0/16", NetworkClass.internal),
        (ScopeKind.cidr, "172.16.0.0/16", "172.16.0.0/16", NetworkClass.internal),
        (ScopeKind.cidr, "fd00:1234::/48", "fd00:1234::/48", NetworkClass.internal),
        (ScopeKind.cidr, "2606:4700::/48", "2606:4700::/48", NetworkClass.external),
    ],
)
def test_ip_and_cidr_rules_derive_their_network_class(
    kind: ScopeKind, raw: str, value: str, net_class: NetworkClass
) -> None:
    rule = build_rule(kind, raw)
    assert rule.value == value
    assert rule.network_class is net_class


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize(
    ("kind", "raw", "why"),
    [
        (ScopeKind.cidr, "0.0.0.0/0", "too broad"),
        (ScopeKind.cidr, "10.0.0.0/8", "too broad"),
        (ScopeKind.cidr, "::/0", "too broad"),
        (ScopeKind.cidr, "2001:db8::/32", "too broad"),
        (ScopeKind.cidr, "10.0.0.5/16", "host bits"),
        (ScopeKind.cidr, "not-a-cidr", "invalid"),
        (ScopeKind.cidr, "10.0.0.0", "invalid"),
        (ScopeKind.cidr, "192.0.0.0/16", "mixes"),
        (ScopeKind.ip, "127.0.0.1", "blocked"),
        (ScopeKind.ip, "169.254.169.254", "blocked"),
        (ScopeKind.ip, "0.0.0.0", "blocked"),
        (ScopeKind.ip, "224.0.0.1", "blocked"),
        (ScopeKind.ip, "255.255.255.255", "blocked"),
        (ScopeKind.ip, "::1", "blocked"),
        (ScopeKind.ip, "fe80::1", "blocked"),
        (ScopeKind.ip, "fd00:ec2::254", "blocked"),  # AWS IPv6 metadata
        (ScopeKind.ip, "100.100.100.200", "blocked"),  # Alibaba metadata
        (ScopeKind.cidr, "127.0.0.0/16", "blocked"),
        (ScopeKind.cidr, "169.254.0.0/16", "blocked"),
        (ScopeKind.cidr, "224.0.0.0/16", "blocked"),
        (ScopeKind.cidr, "fe80::/64", "blocked"),
        (ScopeKind.domain, "com", "single label"),
        (ScopeKind.domain, "*.example.com", "wildcard"),
        (ScopeKind.domain, "127.1", "numeric"),
        (ScopeKind.domain, "", "empty"),
    ],
)
def test_dangerous_or_malformed_rules_are_rejected(kind: ScopeKind, raw: str, why: str) -> None:
    with pytest.raises(InvalidScopeEntryError):
        build_rule(kind, raw)


@pytest.mark.unit
def test_subdomain_flag_is_only_valid_for_domains() -> None:
    with pytest.raises(InvalidScopeEntryError, match="subdomains"):
        build_rule(ScopeKind.cidr, "93.184.216.0/24", include_subdomains=True)


@pytest.mark.unit
def test_limits_are_configurable() -> None:
    loose = ScopeLimits(min_prefix_v4=8)
    assert build_rule(ScopeKind.cidr, "10.0.0.0/8", limits=loose).value == "10.0.0.0/8"
    with pytest.raises(InvalidScopeEntryError):
        build_rule(ScopeKind.cidr, "10.0.0.0/20", limits=ScopeLimits(min_prefix_v4=24))
