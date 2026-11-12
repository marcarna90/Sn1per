"""DNS resolver port and adapters.

The engine depends only on the :class:`Resolver` protocol, so core logic is testable
without a network and workers can be pointed at an internal resolver.
"""

from collections.abc import Mapping, Sequence
from typing import Any, Protocol

import dns.exception
import dns.resolver

from neo_orchestro.scope.types import NoSuchDomainError, ResolutionError


class Resolver(Protocol):
    def resolve(self, hostname: str) -> Sequence[str]:
        """Return every A/AAAA address for ``hostname``.

        Raises:
            NoSuchDomainError: NXDOMAIN, or the name has no address records.
            ResolutionError: any other failure (timeout, SERVFAIL). Callers fail closed.
        """
        ...


class StaticResolver:
    """In-memory resolver: tests, air-gapped labs, and ``/etc/hosts``-style pinning.

    A mapped value may be an exception instance to simulate a failure.
    """

    def __init__(self, mapping: Mapping[str, Sequence[str] | Exception]) -> None:
        self._mapping = dict(mapping)

    def resolve(self, hostname: str) -> Sequence[str]:
        try:
            answer = self._mapping[hostname]
        except KeyError:
            raise NoSuchDomainError(hostname) from None
        if isinstance(answer, Exception):
            raise answer
        return answer


class _DnsLike(Protocol):
    def resolve(self, qname: str, rdtype: str, lifetime: float | None = None) -> Any: ...


class DnsPythonResolver:
    """Production resolver built on dnspython, with bounded lifetime.

    Queries both A and AAAA. If either family cannot be answered reliably the whole
    resolution fails: validating only part of the answer set would defeat pinning.
    """

    def __init__(self, *, timeout: float = 5.0, resolver: _DnsLike | None = None) -> None:
        self._timeout = timeout
        # dns.resolver.Resolver.resolve has a wider signature than _DnsLike; duck-typed on purpose.
        self._resolver: Any = resolver or dns.resolver.Resolver()

    def resolve(self, hostname: str) -> Sequence[str]:
        qname = hostname if hostname.endswith(".") else f"{hostname}."  # absolute: no search list
        addresses: list[str] = []
        for rdtype in ("A", "AAAA"):
            try:
                answer = self._resolver.resolve(qname, rdtype, lifetime=self._timeout)
            except dns.resolver.NXDOMAIN:
                raise NoSuchDomainError(hostname) from None
            except dns.resolver.NoAnswer:
                continue
            except dns.exception.DNSException as exc:
                raise ResolutionError(f"{rdtype} lookup failed: {type(exc).__name__}") from exc
            addresses.extend(str(record.address) for record in answer)
        if not addresses:
            raise NoSuchDomainError(hostname)
        return addresses
