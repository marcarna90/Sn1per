"""``dns_recon``: enumerate DNS records of an authorised domain (Phase 2 reconnaissance).

It only *queries DNS about* the target; it never connects to the target's hosts, so no
pinned address is needed. Engines that do connect must use ``ctx.pinned_ips``.
"""

from collections.abc import Iterator, Mapping
from typing import Any, Protocol

import dns.exception
import dns.resolver

from neo_orchestro.core.enums import FindingCategory, ScopeKind, Severity
from neo_orchestro.engines.base import EngineContext, EngineError
from neo_orchestro.engines.findings import NormalisedFinding

ALLOWED_RECORD_TYPES = ("A", "AAAA", "MX", "NS", "TXT", "CNAME", "SOA")
DEFAULT_RECORD_TYPES = ["A", "AAAA", "MX", "NS", "TXT"]


class DnsClient(Protocol):
    def query(self, name: str, rdtype: str) -> list[str]:
        """Return the records as text. ``[]`` when none exist; ``EngineError`` on failure."""
        ...


class DnsPythonClient:
    def __init__(self, *, timeout: float = 5.0, resolver: Any = None) -> None:
        self._timeout = timeout
        self._resolver: Any = resolver or dns.resolver.Resolver()

    def query(self, name: str, rdtype: str) -> list[str]:
        try:
            answer = self._resolver.resolve(f"{name}.", rdtype, lifetime=self._timeout)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
            return []
        except dns.exception.DNSException as exc:
            raise EngineError("dns_error", f"{rdtype} lookup failed: {type(exc).__name__}") from exc
        return [record.to_text() for record in answer]


class DnsReconEngine:
    name = "dns_recon"
    description = "Enumerate DNS records of a domain and flag a missing SPF policy."
    target_kinds = frozenset({ScopeKind.domain})

    def __init__(self, client: DnsClient) -> None:
        self._client = client

    def validate_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        unknown = sorted(str(key)[:40] for key in set(params) - {"record_types"})
        if unknown:
            raise EngineError("invalid_params", f"unknown parameter(s): {', '.join(unknown)}")
        raw = params.get("record_types", DEFAULT_RECORD_TYPES)
        if not isinstance(raw, list) or not raw:
            raise EngineError("invalid_params", "record_types must be a non-empty list")
        types: list[str] = []
        for item in raw:
            kind = item.upper() if isinstance(item, str) else ""
            if kind not in ALLOWED_RECORD_TYPES:
                raise EngineError(
                    "invalid_params",
                    f"unsupported record type; allowed: {', '.join(ALLOWED_RECORD_TYPES)}",
                )
            if kind in types:
                raise EngineError("invalid_params", "record_types must not contain duplicates")
            types.append(kind)
        return {"record_types": types}

    def run(self, ctx: EngineContext) -> Iterator[NormalisedFinding]:
        record_types: list[str] = list(ctx.params["record_types"])
        txt_values: list[str] = []
        for rdtype in record_types:
            ctx.check()
            for value in self._client.query(ctx.target, rdtype):
                if rdtype == "TXT":
                    txt_values.append(value)
                yield NormalisedFinding(
                    category=FindingCategory.dns_record,
                    severity=Severity.info,
                    title=f"{rdtype} record",
                    asset=ctx.target,
                    description=f"{ctx.target} has a {rdtype} record: {value}",
                    evidence={"type": rdtype, "value": value},
                    key=f"{rdtype}:{value}",
                )
        if "TXT" in record_types and not any("v=spf1" in v.lower() for v in txt_values):
            yield NormalisedFinding(
                category=FindingCategory.misconfiguration,
                severity=Severity.low,
                title="Missing SPF record",
                asset=ctx.target,
                description=(
                    f"No SPF policy was found in the TXT records of {ctx.target}; "
                    "the domain may be easier to spoof in e-mail."
                ),
                evidence={"checked": "TXT"},
                key="spf-missing",
            )
