"""Scope engine threat table (ADR 0004).

Properties under test:
* default deny — nothing runs unless an explicit rule authorises it;
* hard-denied address classes can never be scanned, however they are spelled
  (mapped IPv6, 6to4, NAT64, DNS answers, redirects);
* *every* resolved address is validated, and the validated set is pinned;
* unauthorised / malformed targets are never sent to DNS;
* re-evaluation sees DNS changes (rebinding), redirects are re-validated per hop.
"""

from collections.abc import Sequence

import pytest

from neo_orchestro.core.enums import NetworkClass, ScopeKind
from neo_orchestro.scope import (
    DenyReason,
    NoSuchDomainError,
    RedirectGuard,
    ResolutionError,
    ScopeEngine,
    ScopeRule,
    StaticResolver,
    build_rule,
)

PUBLIC = "93.184.216.34"


class CountingResolver:
    """Wraps a resolver and records every lookup that reaches it."""

    def __init__(self, inner: StaticResolver) -> None:
        self.inner = inner
        self.calls: list[str] = []

    def resolve(self, hostname: str) -> Sequence[str]:
        self.calls.append(hostname)
        return self.inner.resolve(hostname)


class SequenceResolver:
    """Returns a different answer on each call — a DNS-rebinding attacker."""

    def __init__(self, answers: list[list[str]]) -> None:
        self.answers = answers

    def resolve(self, hostname: str) -> Sequence[str]:
        return self.answers.pop(0)


RULES = [
    build_rule(ScopeKind.domain, "example.com", include_subdomains=True, rule_id="r-dom"),
    build_rule(ScopeKind.domain, "single.example.org", rule_id="r-single"),
    build_rule(ScopeKind.ip, PUBLIC, rule_id="r-ip"),
    build_rule(ScopeKind.cidr, "151.101.0.0/16", rule_id="r-cidr"),
    build_rule(ScopeKind.cidr, "10.20.0.0/16", rule_id="r-int"),
    build_rule(ScopeKind.ip, "192.168.1.10", rule_id="r-int-ip"),
]

DNS: dict[str, Sequence[str] | Exception] = {
    "example.com": [PUBLIC],
    "www.example.com": [PUBLIC],
    "single.example.org": ["93.184.216.35"],
    "rebind.example.com": [PUBLIC, "127.0.0.1"],  # one good answer hides a bad one
    "internal.example.com": ["10.20.5.5"],
    "internal-bad.example.com": ["10.99.0.1"],
    "meta.example.com": ["169.254.169.254"],
    "loop6.example.com": ["::1"],
    "mapped.example.com": ["::ffff:127.0.0.1"],
    "linklocal.example.com": ["fe80::1"],
    "nxdomain.example.com": NoSuchDomainError("nxdomain"),
    "timeout.example.com": ResolutionError("timeout"),
    "empty.example.com": [],
    "garbage.example.com": ["not-an-ip"],
    "many.example.com": [f"93.184.{i}.1" for i in range(40)],
    "evil.net": ["203.0.113.9"],
}


@pytest.fixture
def resolver() -> CountingResolver:
    return CountingResolver(StaticResolver(DNS))


@pytest.fixture
def engine(resolver: CountingResolver) -> ScopeEngine:
    return ScopeEngine(RULES, resolver)


# ------------------------------------------------------------------ domains


@pytest.mark.security
def test_exact_domain_is_allowed_and_addresses_are_pinned(engine: ScopeEngine) -> None:
    decision = engine.evaluate("example.com")
    assert decision.allowed
    assert decision.reason is None
    assert decision.pinned_ips == (PUBLIC,)
    assert decision.matched_rule_ids == ("r-dom",)


@pytest.mark.security
def test_subdomains_are_allowed_only_when_the_rule_says_so(engine: ScopeEngine) -> None:
    assert engine.evaluate("www.example.com").allowed
    assert engine.evaluate("single.example.org").allowed
    denied = engine.evaluate("sub.single.example.org")
    assert not denied.allowed
    assert denied.reason is DenyReason.not_in_scope


@pytest.mark.security
@pytest.mark.parametrize(
    "host", ["notexample.com", "evilexample.com", "example.com.evil.net", "example.org", "evil.net"]
)
def test_suffix_confusion_is_not_in_scope(engine: ScopeEngine, host: str) -> None:
    decision = engine.evaluate(host)
    assert not decision.allowed
    assert decision.reason is DenyReason.not_in_scope


@pytest.mark.security
def test_default_deny_with_no_rules(resolver: CountingResolver) -> None:
    decision = ScopeEngine([], resolver).evaluate("example.com")
    assert not decision.allowed
    assert decision.reason is DenyReason.not_in_scope


@pytest.mark.security
def test_one_bad_answer_among_good_ones_denies_the_target(engine: ScopeEngine) -> None:
    decision = engine.evaluate("rebind.example.com")
    assert not decision.allowed
    assert decision.reason is DenyReason.blocked_address
    assert decision.details["ip"] == "127.0.0.1"
    assert decision.details["ip_class"] == "loopback"
    assert decision.pinned_ips == ()  # nothing may be used after a denial


@pytest.mark.security
@pytest.mark.parametrize(
    ("host", "ip_class"),
    [
        ("meta.example.com", "link_local"),
        ("loop6.example.com", "loopback"),
        ("mapped.example.com", "loopback"),
        ("linklocal.example.com", "link_local"),
    ],
)
def test_dns_answers_in_hard_denied_classes_are_blocked(
    engine: ScopeEngine, host: str, ip_class: str
) -> None:
    decision = engine.evaluate(host)
    assert decision.reason is DenyReason.blocked_address
    assert decision.details["ip_class"] == ip_class


@pytest.mark.security
def test_internal_addresses_need_an_explicit_internal_rule(engine: ScopeEngine) -> None:
    ok = engine.evaluate("internal.example.com")
    assert ok.allowed
    assert ok.pinned_ips == ("10.20.5.5",)
    assert set(ok.matched_rule_ids) == {"r-dom", "r-int"}

    bad = engine.evaluate("internal-bad.example.com")
    assert bad.reason is DenyReason.internal_not_authorised


@pytest.mark.security
@pytest.mark.parametrize(
    ("host", "reason"),
    [
        ("nxdomain.example.com", DenyReason.unresolvable),
        ("empty.example.com", DenyReason.unresolvable),
        ("timeout.example.com", DenyReason.resolution_failed),
        ("garbage.example.com", DenyReason.resolution_failed),
        ("many.example.com", DenyReason.too_many_addresses),
    ],
)
def test_resolution_problems_fail_closed(
    engine: ScopeEngine, host: str, reason: DenyReason
) -> None:
    decision = engine.evaluate(host)
    assert not decision.allowed
    assert decision.reason is reason


# ------------------------------------------------------------------ IP targets


@pytest.mark.security
@pytest.mark.parametrize(
    ("ip", "rule_id"),
    [
        (PUBLIC, "r-ip"),
        ("151.101.1.1", "r-cidr"),
        ("10.20.0.1", "r-int"),
        ("192.168.1.10", "r-int-ip"),
    ],
)
def test_authorised_ips_are_allowed(engine: ScopeEngine, ip: str, rule_id: str) -> None:
    decision = engine.evaluate(ip)
    assert decision.allowed
    assert decision.pinned_ips == (ip,)
    assert decision.matched_rule_ids == (rule_id,)


@pytest.mark.security
def test_unlisted_public_ip_is_out_of_scope(engine: ScopeEngine) -> None:
    assert engine.evaluate("8.8.8.8").reason is DenyReason.not_in_scope


@pytest.mark.security
def test_unlisted_private_ip_is_not_authorised(engine: ScopeEngine) -> None:
    assert engine.evaluate("10.21.0.1").reason is DenyReason.internal_not_authorised
    assert engine.evaluate("192.168.1.11").reason is DenyReason.internal_not_authorised


@pytest.mark.security
@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "127.255.255.254",
        "0.0.0.0",
        "169.254.169.254",
        "169.254.170.2",
        "224.0.0.1",
        "239.255.255.250",
        "240.0.0.1",
        "255.255.255.255",
        "::",
        "::1",
        "fe80::1",
        "ff02::1",
        "fd00:ec2::254",  # AWS IPv6 metadata (ULA, so only a explicit denylist catches it)
        "100.100.100.200",  # Alibaba metadata (CGNAT range)
        "192.0.0.192",  # Oracle metadata
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:169.254.169.254",
        "2002:7f00:1::",  # 6to4 embedding 127.0.0.1
        "2002:a9fe:a9fe::",  # 6to4 embedding 169.254.169.254
        "64:ff9b::7f00:1",  # NAT64 embedding 127.0.0.1
    ],
)
def test_hard_denied_ips_are_blocked_in_every_spelling(engine: ScopeEngine, ip: str) -> None:
    decision = engine.evaluate(ip)
    assert not decision.allowed
    assert decision.reason is DenyReason.blocked_address
    assert decision.pinned_ips == ()


@pytest.mark.security
def test_ipv4_mapped_ipv6_matches_rules_against_the_embedded_ipv4(engine: ScopeEngine) -> None:
    decision = engine.evaluate(f"::ffff:{PUBLIC}")
    assert decision.allowed
    assert decision.pinned_ips == (PUBLIC,)  # pinned in canonical IPv4 form


# ------------------------------------------------------------------ no DNS for bad input


@pytest.mark.security
@pytest.mark.parametrize(
    "target", ["", "http://example.com", "127.1", "2130706433", "user@example.com", "a b.com"]
)
def test_malformed_targets_never_reach_dns(
    engine: ScopeEngine, resolver: CountingResolver, target: str
) -> None:
    decision = engine.evaluate(target)
    assert decision.reason is DenyReason.invalid_target
    assert resolver.calls == []


@pytest.mark.security
def test_out_of_scope_names_are_never_resolved(
    engine: ScopeEngine, resolver: CountingResolver
) -> None:
    engine.evaluate("evil.net")
    engine.evaluate("notexample.com")
    assert resolver.calls == []  # no DNS query (and no data exfiltration) for unauthorised names


# ------------------------------------------------------------------ rebinding / TOCTOU


@pytest.mark.security
def test_reevaluation_detects_dns_rebinding() -> None:
    rebinding = SequenceResolver([[PUBLIC], ["127.0.0.1"]])
    engine = ScopeEngine(RULES, rebinding)
    first = engine.evaluate("example.com")  # API-time check
    assert first.allowed
    second = engine.evaluate("example.com")  # worker-time check, DNS has changed
    assert not second.allowed
    assert second.reason is DenyReason.blocked_address


@pytest.mark.security
def test_decision_is_serialisable_for_the_audit_trail(engine: ScopeEngine) -> None:
    data = engine.evaluate("example.com").to_dict()
    assert data == {
        "allowed": True,
        "reason": None,
        "target": "example.com",
        "pinned_ips": [PUBLIC],
        "matched_rule_ids": ["r-dom"],
        "details": {},
    }
    denied = engine.evaluate("evil.net").to_dict()
    assert denied["allowed"] is False
    assert denied["reason"] == "not_in_scope"


@pytest.mark.security
@pytest.mark.parametrize(
    ("value", "claimed", "target", "reason"),
    [
        # private range wrongly labelled "external" must not authorise private addresses
        ("10.0.0.0/16", NetworkClass.external, "10.0.0.1", DenyReason.internal_not_authorised),
        # public range wrongly labelled "internal" must not authorise public addresses
        ("93.184.216.0/24", NetworkClass.internal, "93.184.216.9", DenyReason.not_in_scope),
    ],
)
def test_rules_with_a_tampered_network_class_are_not_trusted(
    value: str, claimed: NetworkClass, target: str, reason: DenyReason
) -> None:
    # Simulates a row edited out-of-band: the engine re-derives the class from the address.
    tampered = ScopeRule(
        id="x",
        kind=ScopeKind.cidr,
        value=value,
        include_subdomains=False,
        network_class=claimed,
    )
    decision = ScopeEngine([tampered], StaticResolver({})).evaluate(target)
    assert not decision.allowed
    assert decision.reason is reason


# ------------------------------------------------------------------ URLs & redirects


@pytest.mark.security
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/path?q=1#frag",
        "http://www.example.com:8080/",
        "http://EXAMPLE.com./",
        "https://10.20.5.5/admin",
    ],
)
def test_in_scope_urls_are_allowed(engine: ScopeEngine, url: str) -> None:
    assert engine.evaluate_url(url).allowed


@pytest.mark.security
@pytest.mark.parametrize(
    ("url", "reason"),
    [
        ("ftp://example.com/", DenyReason.scheme_not_allowed),
        ("file:///etc/passwd", DenyReason.scheme_not_allowed),
        ("javascript:alert(1)", DenyReason.scheme_not_allowed),
        ("gopher://example.com/", DenyReason.scheme_not_allowed),
        ("//example.com/x", DenyReason.scheme_not_allowed),
        ("http://user:pw@example.com/", DenyReason.userinfo_not_allowed),
        ("http://example.com@evil.net/", DenyReason.userinfo_not_allowed),
        ("http://example.com\\@evil.net/", DenyReason.invalid_target),
        ("http://example.com:99999/", DenyReason.invalid_target),
        ("http://example.com:abc/", DenyReason.invalid_target),
        ("http://2130706433/", DenyReason.invalid_target),
        ("http://127.1/", DenyReason.invalid_target),
        ("http://[::1]/", DenyReason.blocked_address),
        ("http://127.0.0.1/", DenyReason.blocked_address),
        ("http://169.254.169.254/latest/meta-data/", DenyReason.blocked_address),
        ("http://evil.net/", DenyReason.not_in_scope),
        ("http://exa mple.com/", DenyReason.invalid_target),
        ("", DenyReason.invalid_target),
    ],
)
def test_dangerous_urls_are_denied(engine: ScopeEngine, url: str, reason: DenyReason) -> None:
    decision = engine.evaluate_url(url)
    assert not decision.allowed
    assert decision.reason is reason


@pytest.mark.security
def test_redirects_are_validated_hop_by_hop(engine: ScopeEngine) -> None:
    guard = RedirectGuard(engine, max_hops=10)  # six independent probes below
    start = "https://example.com/start"

    assert guard.follow(start, "/login").allowed  # relative, same host
    assert guard.follow(start, "https://www.example.com/a").allowed  # in-scope absolute
    assert guard.follow(start, "//evil.net/x").reason is DenyReason.not_in_scope  # proto-relative
    assert guard.follow(start, "http://127.0.0.1/admin").reason is DenyReason.blocked_address
    assert guard.follow(start, "http://169.254.169.254/").reason is DenyReason.blocked_address
    assert guard.follow(start, "ftp://example.com/").reason is DenyReason.scheme_not_allowed


@pytest.mark.security
def test_redirect_chains_are_bounded(engine: ScopeEngine) -> None:
    guard = RedirectGuard(engine, max_hops=2)
    url = "https://example.com/"
    assert guard.follow(url, "/a").allowed
    assert guard.follow(url, "/b").allowed
    third = guard.follow(url, "/c")
    assert not third.allowed
    assert third.reason is DenyReason.too_many_redirects
