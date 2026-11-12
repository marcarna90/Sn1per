"""Strict target parsing. Anything ambiguous is rejected rather than guessed.

Why so strict: resolvers and ``inet_aton`` accept forms such as ``2130706433``,
``0x7f.1``, ``127.1`` or ``0177.0.0.1`` as 127.0.0.1. A target that *looks* like a
harmless host name but is read as a loopback address is a classic SSRF bypass, so
numeric-looking hosts that are not a canonical dotted-quad are refused outright.
"""

import re
import unicodedata
from ipaddress import IPv4Address, IPv6Address, ip_address

from neo_orchestro.core.enums import ScopeKind
from neo_orchestro.scope.types import InvalidTargetError, ParsedTarget

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_FORBIDDEN_CHARS = frozenset("/\\@%[]*?#&=+;,<>\"'`|{}^~")
_MAX_DOMAIN_LENGTH = 253


def has_control_or_space(text: str) -> bool:
    """True if ``text`` holds control, format (e.g. RTL override) or whitespace characters."""
    return any(unicodedata.category(char)[0] in {"C", "Z"} for char in text)


def _check_characters(text: str) -> None:
    for char in text:
        if char in _FORBIDDEN_CHARS:
            raise InvalidTargetError(f"character {char!r} is not allowed in a target")
    if has_control_or_space(text):
        raise InvalidTargetError("control, formatting and whitespace characters are not allowed")


def normalise_domain(text: str) -> str:
    """Lowercase, IDNA-encode and validate a fully-qualified domain name."""
    name = text[:-1] if text.endswith(".") else text
    try:
        name = name.encode("idna").decode("ascii") if not name.isascii() else name
    except UnicodeError as exc:
        raise InvalidTargetError("invalid internationalised domain name") from exc
    name = name.lower()
    if len(name) > _MAX_DOMAIN_LENGTH:
        raise InvalidTargetError("domain name is too long")
    labels = name.split(".")
    if len(labels) < 2:
        raise InvalidTargetError(
            "a fully-qualified domain name with at least two labels is required"
        )
    if not all(_LABEL.fullmatch(label) for label in labels):
        raise InvalidTargetError("domain contains an invalid label")
    if not any(char.isalpha() for char in labels[-1]):
        # All-numeric last label ⇒ may be parsed as an IP address by the OS resolver.
        raise InvalidTargetError("top-level label must not be purely numeric")
    return name


def format_ip(ip: IPv4Address | IPv6Address) -> str:
    """Canonical text, identical on every supported Python version.

    Python 3.13 prints IPv4-mapped IPv6 in dotted form while 3.12 prints hex groups;
    we pin one spelling so stored values and comparisons never depend on the runtime.
    """
    if isinstance(ip, IPv6Address) and ip.ipv4_mapped is not None:
        return f"::ffff:{ip.ipv4_mapped}"
    return str(ip)


def parse_target(raw: str) -> ParsedTarget:
    """Parse a scan target: a domain name or an IP literal. Nothing else."""
    if not isinstance(raw, str):
        raise InvalidTargetError("target must be a string")
    text = raw.strip(" ")
    if not text:
        raise InvalidTargetError("target is empty")
    _check_characters(text)

    if ":" in text:
        try:
            ip = ip_address(text)
        except ValueError as exc:
            raise InvalidTargetError(
                "not a valid IPv6 address (ports and URLs are not accepted)"
            ) from exc
        if not isinstance(ip, IPv6Address):  # pragma: no cover - ':' implies IPv6
            raise InvalidTargetError("not a valid IPv6 address")
        return ParsedTarget(ScopeKind.ip, format_ip(ip))

    if all(char.isdigit() or char == "." for char in text):
        try:
            ip4 = IPv4Address(text)
        except ValueError as exc:
            raise InvalidTargetError(
                "numeric hosts must be a canonical dotted-quad IPv4 address"
            ) from exc
        return ParsedTarget(ScopeKind.ip, str(ip4))

    return ParsedTarget(ScopeKind.domain, normalise_domain(text))
