"""DNS adapters: static (tests/air-gapped labs) and dnspython (production)."""

from typing import Any

import dns.exception
import dns.resolver
import pytest

from neo_orchestro.core.dns import build_resolver
from neo_orchestro.scope import (
    DnsPythonResolver,
    NoSuchDomainError,
    ResolutionError,
    StaticResolver,
)


class _Rdata:
    def __init__(self, address: str) -> None:
        self.address = address


class _StubDnsResolver:
    """Mimics ``dns.resolver.Resolver.resolve`` for A / AAAA."""

    def __init__(self, table: dict[str, Any]) -> None:
        self.table = table
        self.calls: list[tuple[str, str, float | None]] = []

    def resolve(self, qname: str, rdtype: str, lifetime: float | None = None) -> list[_Rdata]:
        self.calls.append((qname, rdtype, lifetime))
        result = self.table[rdtype]
        if isinstance(result, Exception):
            raise result
        return [_Rdata(a) for a in result]


@pytest.mark.unit
def test_static_resolver_returns_configured_addresses() -> None:
    resolver = StaticResolver({"example.com": ["93.184.216.34"]})
    assert list(resolver.resolve("example.com")) == ["93.184.216.34"]


@pytest.mark.unit
def test_static_resolver_unknown_name_is_nxdomain() -> None:
    with pytest.raises(NoSuchDomainError):
        StaticResolver({}).resolve("nope.example.com")


@pytest.mark.unit
def test_static_resolver_can_simulate_failures() -> None:
    resolver = StaticResolver({"slow.example.com": ResolutionError("timeout")})
    with pytest.raises(ResolutionError):
        resolver.resolve("slow.example.com")


@pytest.mark.unit
def test_dnspython_resolver_merges_a_and_aaaa_and_uses_an_absolute_name() -> None:
    stub = _StubDnsResolver({"A": ["93.184.216.34"], "AAAA": ["2606:2800:220:1::1"]})
    resolver = DnsPythonResolver(timeout=3.0, resolver=stub)
    assert list(resolver.resolve("example.com")) == ["93.184.216.34", "2606:2800:220:1::1"]
    assert {c[0] for c in stub.calls} == {"example.com."}  # absolute: no search-list expansion
    assert {c[2] for c in stub.calls} == {3.0}  # bounded lifetime


@pytest.mark.unit
def test_dnspython_resolver_tolerates_a_family_without_records() -> None:
    stub = _StubDnsResolver({"A": ["93.184.216.34"], "AAAA": dns.resolver.NoAnswer()})
    assert list(DnsPythonResolver(resolver=stub).resolve("example.com")) == ["93.184.216.34"]


@pytest.mark.unit
def test_dnspython_resolver_maps_nxdomain_and_empty_answers() -> None:
    with pytest.raises(NoSuchDomainError):
        DnsPythonResolver(
            resolver=_StubDnsResolver({"A": dns.resolver.NXDOMAIN(), "AAAA": []})
        ).resolve("x.example.com")
    with pytest.raises(NoSuchDomainError):
        DnsPythonResolver(
            resolver=_StubDnsResolver(
                {"A": dns.resolver.NoAnswer(), "AAAA": dns.resolver.NoAnswer()}
            )
        ).resolve("x.example.com")


@pytest.mark.unit
@pytest.mark.parametrize("failure", [dns.exception.Timeout(), dns.resolver.NoNameservers()])
def test_dnspython_resolver_fails_closed_on_infrastructure_errors(failure: Exception) -> None:
    # If we cannot see *all* addresses we must not pretend we validated them.
    stub = _StubDnsResolver({"A": ["93.184.216.34"], "AAAA": failure})
    with pytest.raises(ResolutionError):
        DnsPythonResolver(resolver=stub).resolve("example.com")


@pytest.mark.unit
def test_build_resolver_uses_exactly_the_configured_nameservers() -> None:
    resolver = build_resolver(["9.9.9.9", "2606:4700:4700::1111"])
    assert resolver.nameservers == ["9.9.9.9", "2606:4700:4700::1111"]
    assert resolver.search == []  # nothing is read from the host's resolv.conf


@pytest.mark.unit
def test_build_resolver_without_nameservers_follows_the_system_configuration() -> None:
    assert isinstance(build_resolver([]), dns.resolver.Resolver)


@pytest.mark.unit
def test_the_scope_resolver_is_built_with_the_configured_nameservers() -> None:
    resolver = DnsPythonResolver(nameservers=["192.0.2.53"])
    assert resolver._resolver.nameservers == ["192.0.2.53"]
