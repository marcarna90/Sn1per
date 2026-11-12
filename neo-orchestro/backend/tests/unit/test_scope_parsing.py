"""Target parsing & normalisation: strict, no ambiguous host forms (ADR 0004)."""

import pytest

from neo_orchestro.core.enums import ScopeKind
from neo_orchestro.scope import InvalidTargetError, parse_target


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "kind", "value"),
    [
        ("example.com", ScopeKind.domain, "example.com"),
        ("Example.COM", ScopeKind.domain, "example.com"),
        ("example.com.", ScopeKind.domain, "example.com"),
        ("  example.com  ", ScopeKind.domain, "example.com"),
        ("sub.deep.example.com", ScopeKind.domain, "sub.deep.example.com"),
        ("bücher.example", ScopeKind.domain, "xn--bcher-kva.example"),
        ("a-b.example.org", ScopeKind.domain, "a-b.example.org"),
        ("93.184.216.34", ScopeKind.ip, "93.184.216.34"),
        ("2001:db8::1", ScopeKind.ip, "2001:db8::1"),
        ("2001:0DB8:0:0:0:0:0:1", ScopeKind.ip, "2001:db8::1"),
        ("::ffff:93.184.216.34", ScopeKind.ip, "::ffff:93.184.216.34"),
    ],
)
def test_valid_targets_are_normalised(raw: str, kind: ScopeKind, value: str) -> None:
    parsed = parse_target(raw)
    assert parsed.kind is kind
    assert parsed.value == value


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "http://example.com",  # a URL is not a host
        "example.com/path",
        "example.com:80",  # ports are not part of a target
        "user@example.com",
        "example.com\\@evil.com",
        "exa mple.com",
        "example.com\n",
        "example.com\x00",
        "exa\u202emple.com",  # right-to-left override
        "ex%61mple.com",  # percent-encoding
        "*.example.com",  # wildcard is expressed by a scope flag, not in a target
        "example..com",
        ".example.com",
        "-bad.example.com",
        "bad-.example.com",
        "a_b.example.com",
        "a" * 64 + ".example.com",
        "a." * 127 + "com",  # > 253 chars
        "example",  # single label (localhost, intranet host names, TLDs)
        "localhost",
        # numeric host forms that resolvers/`inet_aton` read as IP addresses:
        "2130706433",  # decimal 127.0.0.1
        "0x7f.1",
        "127.1",
        "0177.0.0.1",  # octal
        "010.0.0.1",
        "1.2.3",
        "256.1.1.1",
        "example.123",  # all-numeric TLD
        # IPv6 decorations:
        "[::1]",
        "fe80::1%eth0",
        "::1/128",
    ],
)
def test_ambiguous_or_malformed_targets_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidTargetError):
        parse_target(raw)


@pytest.mark.unit
def test_non_string_input_is_rejected() -> None:
    with pytest.raises(InvalidTargetError):
        parse_target(None)  # type: ignore[arg-type]
