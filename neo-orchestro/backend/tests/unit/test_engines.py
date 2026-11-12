"""Engine framework: normalised findings, allowlist registry, dns_recon engine."""

import uuid
from collections.abc import Mapping
from typing import Any

import pytest

from neo_orchestro.core.config import Settings
from neo_orchestro.core.enums import FindingCategory, ScopeKind, Severity
from neo_orchestro.engines import (
    DnsReconEngine,
    EngineContext,
    EngineError,
    EngineRegistry,
    NormalisedFinding,
    ScanCancelled,
    UnknownEngineError,
    default_registry,
)


def finding(**kw: Any) -> NormalisedFinding:
    base: dict[str, Any] = {
        "category": FindingCategory.dns_record,
        "severity": Severity.info,
        "title": "A record",
        "asset": "example.com",
        "key": "A:93.184.216.34",
    }
    return NormalisedFinding(**{**base, **kw})


# ------------------------------------------------------------------ findings


@pytest.mark.unit
def test_fingerprints_are_stable_and_ignore_volatile_evidence() -> None:
    a = finding(evidence={"ttl": 300})
    b = finding(evidence={"ttl": 60, "seen": "later"})
    assert a.fingerprint == b.fingerprint
    assert len(a.fingerprint) == 64


@pytest.mark.unit
@pytest.mark.parametrize(
    "change",
    [
        {"asset": "other.com"},
        {"title": "AAAA record"},
        {"key": "A:1.1.1.1"},
        {"category": FindingCategory.info},
    ],
)
def test_fingerprints_change_with_identity(change: dict[str, Any]) -> None:
    assert finding().fingerprint != finding(**change).fingerprint


@pytest.mark.unit
def test_fingerprint_fields_cannot_be_confused_by_concatenation() -> None:
    assert finding(title="ab", key="c").fingerprint != finding(title="a", key="bc").fingerprint


@pytest.mark.unit
def test_findings_are_immutable_and_bounded() -> None:
    f = finding()
    with pytest.raises(Exception, match="frozen"):
        f.title = "changed"  # type: ignore[misc]
    with pytest.raises(ValueError, match="title"):
        finding(title="x" * 301)


# ------------------------------------------------------------------ registry


class _Engine:
    name = "demo"
    description = "demo engine"
    target_kinds = frozenset({ScopeKind.domain})

    def validate_params(self, params: Mapping[str, Any]) -> dict[str, Any]:
        return dict(params)

    def run(self, ctx: EngineContext) -> Any:
        return iter(())


@pytest.mark.unit
@pytest.mark.security
def test_only_registered_engines_can_be_resolved() -> None:
    registry = EngineRegistry([_Engine()])
    assert registry.get("demo").name == "demo"
    for hostile in ["nmap", "demo; rm -rf /", "../demo", "DEMO", "", "demo ", "$(id)"]:
        with pytest.raises(UnknownEngineError):
            registry.get(hostile)


@pytest.mark.unit
def test_registry_rejects_duplicates_and_bad_names() -> None:
    registry = EngineRegistry([_Engine()])
    with pytest.raises(ValueError, match="already registered"):
        registry.register(_Engine())
    bad = _Engine()
    bad.name = "Bad Name!"
    with pytest.raises(ValueError, match="engine name"):
        EngineRegistry([bad])


@pytest.mark.unit
def test_default_registry_contains_dns_recon(settings_for_registry: Settings) -> None:
    registry = default_registry(settings_for_registry)
    assert [e.name for e in registry.all()] == ["dns_recon"]


@pytest.fixture
def settings_for_registry() -> Settings:
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        secret_key="k" * 64,
        database_url="postgresql+pg8000://u:p@localhost/db",
        redis_url="redis://localhost:6379/0",
    )


# ------------------------------------------------------------------ dns_recon


class FakeDns:
    def __init__(self, table: Mapping[str, Any]) -> None:
        self.table = table
        self.queries: list[tuple[str, str]] = []

    def query(self, name: str, rdtype: str) -> list[str]:
        self.queries.append((name, rdtype))
        answer = self.table.get(rdtype, [])
        if isinstance(answer, Exception):
            raise answer
        return list(answer)


def ctx(
    target: str = "example.com", params: Mapping[str, Any] | None = None, **kw: Any
) -> EngineContext:
    return EngineContext(
        scan_id=uuid.uuid4(),
        target=target,
        pinned_ips=("93.184.216.34",),
        params=params or {},
        is_cancelled=kw.pop("is_cancelled", lambda: False),
        deadline=kw.pop("deadline", None),
    )


@pytest.mark.unit
def test_dns_recon_is_a_domain_engine() -> None:
    engine = DnsReconEngine(FakeDns({}))
    assert engine.name == "dns_recon"
    assert engine.target_kinds == frozenset({ScopeKind.domain})


@pytest.mark.unit
def test_dns_recon_maps_records_to_normalised_findings() -> None:
    dns = FakeDns(
        {
            "A": ["93.184.216.34"],
            "MX": ["10 mail.example.com."],
            "TXT": ['"v=spf1 -all"'],
        }
    )
    engine = DnsReconEngine(dns)
    params = engine.validate_params({})
    results = list(engine.run(ctx(params=params)))

    by_title = {f.title: f for f in results}
    assert {"A record", "MX record", "TXT record"} <= set(by_title)
    a = by_title["A record"]
    assert (a.category, a.severity, a.asset) == (
        FindingCategory.dns_record,
        Severity.info,
        "example.com",
    )
    assert a.evidence == {"type": "A", "value": "93.184.216.34"}
    assert not any(f.category is FindingCategory.misconfiguration for f in results)  # SPF present
    assert len({f.fingerprint for f in results}) == len(results)


@pytest.mark.unit
def test_dns_recon_flags_a_missing_spf_record() -> None:
    engine = DnsReconEngine(FakeDns({"TXT": ['"google-site-verification=abc"']}))
    results = list(engine.run(ctx(params=engine.validate_params({"record_types": ["TXT"]}))))
    spf = [f for f in results if f.category is FindingCategory.misconfiguration]
    assert len(spf) == 1
    assert spf[0].severity is Severity.low
    assert spf[0].title == "Missing SPF record"


@pytest.mark.unit
def test_dns_recon_only_queries_the_requested_record_types() -> None:
    dns = FakeDns({"A": ["93.184.216.34"], "NS": ["ns1.example.com."]})
    engine = DnsReconEngine(dns)
    list(engine.run(ctx(params=engine.validate_params({"record_types": ["a", "ns"]}))))
    assert [q[1] for q in dns.queries] == ["A", "NS"]  # normalised to upper case, in order
    assert {q[0] for q in dns.queries} == {"example.com"}  # only the authorised target is queried


@pytest.mark.unit
@pytest.mark.security
@pytest.mark.parametrize(
    "params",
    [
        {"record_types": ["AXFR"]},
        {"record_types": ["A", "A"]},
        {"record_types": "A"},
        {"record_types": []},
        {"record_types": ["A" * 20]},
        {"nameserver": "8.8.8.8"},
        {"command": "dig"},
    ],
)
def test_dns_recon_rejects_unknown_or_dangerous_params(params: dict[str, Any]) -> None:
    with pytest.raises(EngineError) as caught:
        DnsReconEngine(FakeDns({})).validate_params(params)
    assert caught.value.code == "invalid_params"


@pytest.mark.unit
def test_dns_recon_defaults() -> None:
    assert DnsReconEngine(FakeDns({})).validate_params({}) == {
        "record_types": ["A", "AAAA", "MX", "NS", "TXT"]
    }


@pytest.mark.unit
def test_dns_recon_stops_when_cancelled() -> None:
    engine = DnsReconEngine(FakeDns({"A": ["1.2.3.4"]}))
    with pytest.raises(ScanCancelled):
        list(engine.run(ctx(is_cancelled=lambda: True, params=engine.validate_params({}))))


@pytest.mark.unit
def test_dns_recon_stops_at_the_deadline() -> None:
    engine = DnsReconEngine(FakeDns({"A": ["1.2.3.4"]}))
    with pytest.raises(EngineError) as caught:
        list(engine.run(ctx(deadline=0.0, params=engine.validate_params({}))))
    assert caught.value.code == "timeout"


@pytest.mark.unit
def test_dns_failures_surface_as_engine_errors() -> None:
    engine = DnsReconEngine(FakeDns({"A": EngineError("dns_error", "timed out")}))
    with pytest.raises(EngineError) as caught:
        list(engine.run(ctx(params=engine.validate_params({"record_types": ["A"]}))))
    assert caught.value.code == "dns_error"


@pytest.mark.unit
def test_default_registry_points_dns_recon_at_the_configured_nameservers() -> None:
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        secret_key="k" * 64,
        database_url="postgresql+pg8000://u:p@localhost/db",
        redis_url="redis://localhost:6379/0",
        dns_nameservers="192.0.2.53",
    )
    engine = default_registry(settings).get("dns_recon")
    assert engine._client._resolver.nameservers == ["192.0.2.53"]  # type: ignore[attr-defined]
