"""The scope engine: default-deny evaluation of scan targets (ADR 0004).

Guarantees:

* **Default deny.** A target runs only if an explicit rule authorises it.
* **No DNS for unauthorised input.** Malformed or out-of-scope names are refused
  *before* any lookup, so the platform cannot be used to leak data through DNS.
* **Every address is validated** and the validated set is returned as ``pinned_ips``;
  executors connect to those, never to a fresh resolution (anti-rebinding).
* **Hard-denied classes** (loopback, link-local, multicast, reserved, metadata) can
  never be scanned, in any spelling, via DNS answers, or via redirects.
"""

from collections.abc import Iterable
from ipaddress import ip_address, ip_network
from urllib.parse import urljoin, urlsplit

from neo_orchestro.core.enums import NetworkClass, ScopeKind
from neo_orchestro.scope.network import IPAddress, IPNetwork, classify_ip, normalise_ip
from neo_orchestro.scope.parsing import format_ip, has_control_or_space, parse_target
from neo_orchestro.scope.resolver import Resolver
from neo_orchestro.scope.types import (
    HARD_DENIED,
    Decision,
    DenyReason,
    InvalidTargetError,
    IpClass,
    NoSuchDomainError,
    ResolutionError,
    ScopeLimits,
    ScopeRule,
)

_ALLOWED_SCHEMES = frozenset({"http", "https"})


def _deny(reason: DenyReason, target: str | None = None, **details: str) -> Decision:
    return Decision(allowed=False, reason=reason, target=target, details=dict(details))


class ScopeEngine:
    """Evaluate targets against an organisation's rules. Cheap to build; build one per call site."""

    def __init__(
        self,
        rules: Iterable[ScopeRule],
        resolver: Resolver,
        *,
        limits: ScopeLimits | None = None,
    ) -> None:
        self._resolver = resolver
        self._limits = limits or ScopeLimits()
        self._domain_rules: list[ScopeRule] = []
        self._network_rules: list[tuple[ScopeRule, IPNetwork]] = []
        for rule in rules:
            if rule.kind is ScopeKind.domain:
                self._domain_rules.append(rule)
            else:
                try:
                    network = ip_network(rule.value, strict=False)
                except ValueError:
                    continue  # unreadable rule ⇒ authorises nothing (fail closed)
                self._network_rules.append((rule, network))

    # ------------------------------------------------------------------ public API

    def evaluate(self, raw_target: str) -> Decision:
        """Decide whether ``raw_target`` (domain or IP literal) may be scanned."""
        try:
            parsed = parse_target(raw_target)
        except InvalidTargetError as exc:
            return _deny(DenyReason.invalid_target, message=str(exc))
        if parsed.kind is ScopeKind.ip:
            return self._evaluate_ip(ip_address(parsed.value))
        return self._evaluate_domain(parsed.value)

    def evaluate_url(self, raw_url: str) -> Decision:
        """Decide whether an HTTP(S) URL (e.g. a redirect target) may be requested."""
        if not isinstance(raw_url, str) or not raw_url:
            return _deny(DenyReason.invalid_target, message="URL is empty")
        if has_control_or_space(raw_url):
            return _deny(DenyReason.invalid_target, message="control or whitespace characters")
        if "\\" in raw_url:
            return _deny(DenyReason.invalid_target, message="backslash is not allowed in a URL")
        try:
            parts = urlsplit(raw_url)
            port = parts.port
        except ValueError:
            return _deny(DenyReason.invalid_target, message="malformed URL or port")
        if parts.scheme.lower() not in _ALLOWED_SCHEMES:
            return _deny(DenyReason.scheme_not_allowed, scheme=parts.scheme or "(none)")
        if "@" in parts.netloc:
            return _deny(DenyReason.userinfo_not_allowed)
        if not parts.hostname:
            return _deny(DenyReason.invalid_target, message="URL has no host")
        if port is not None and not 1 <= port <= 65535:
            return _deny(DenyReason.invalid_target, message="port out of range")
        return self.evaluate(parts.hostname)

    # ------------------------------------------------------------------ internals

    def _evaluate_ip(self, raw_ip: IPAddress) -> Decision:
        ip = normalise_ip(raw_ip)
        ip_class = classify_ip(ip)
        text = format_ip(ip) if ip.version == 6 else str(ip)
        if ip_class in HARD_DENIED:
            return _deny(DenyReason.blocked_address, text, ip=text, ip_class=ip_class.value)
        matched = self._matching_network_rules(ip, ip_class)
        if not matched:
            reason = (
                DenyReason.internal_not_authorised
                if ip_class is IpClass.private
                else DenyReason.not_in_scope
            )
            return _deny(reason, text, ip=text)
        return Decision(
            allowed=True,
            target=text,
            pinned_ips=(text,),
            matched_rule_ids=tuple(matched),
        )

    def _evaluate_domain(self, host: str) -> Decision:
        domain_matches = [r.id for r in self._domain_rules if _domain_in_rule(host, r)]
        if not domain_matches:
            return _deny(DenyReason.not_in_scope, host)  # no DNS query for unauthorised names

        try:
            answers = list(self._resolver.resolve(host))
        except NoSuchDomainError:
            return _deny(DenyReason.unresolvable, host)
        except ResolutionError as exc:
            return _deny(DenyReason.resolution_failed, host, message=str(exc))

        addresses: list[IPAddress] = []
        for answer in answers:
            try:
                ip = normalise_ip(ip_address(answer))
            except ValueError:
                return _deny(
                    DenyReason.resolution_failed, host, message="resolver returned a non-IP"
                )
            if ip not in addresses:
                addresses.append(ip)
        if not addresses:
            return _deny(DenyReason.unresolvable, host)
        if len(addresses) > self._limits.max_resolved_ips:
            return _deny(DenyReason.too_many_addresses, host, count=str(len(addresses)))

        matched: list[str] = list(domain_matches)
        for ip in addresses:
            ip_class = classify_ip(ip)
            text = format_ip(ip) if ip.version == 6 else str(ip)
            if ip_class in HARD_DENIED:
                return _deny(DenyReason.blocked_address, host, ip=text, ip_class=ip_class.value)
            if ip_class is IpClass.private:
                rules = self._matching_network_rules(ip, ip_class)
                if not rules:
                    return _deny(DenyReason.internal_not_authorised, host, ip=text)
                matched.extend(r for r in rules if r not in matched)
        pinned = tuple(format_ip(ip) if ip.version == 6 else str(ip) for ip in addresses)
        return Decision(
            allowed=True,
            target=host,
            pinned_ips=pinned,
            matched_rule_ids=tuple(matched),
        )

    def _matching_network_rules(self, ip: IPAddress, ip_class: IpClass) -> list[str]:
        """Rules whose range contains ``ip`` *and* whose declared class agrees with reality."""
        wanted = NetworkClass.internal if ip_class is IpClass.private else NetworkClass.external
        return [
            rule.id
            for rule, network in self._network_rules
            if rule.network_class is wanted and network.version == ip.version and ip in network
        ]


def _domain_in_rule(host: str, rule: ScopeRule) -> bool:
    if host == rule.value:
        return True
    # Dot boundary: "notexample.com" must NOT match a rule for "example.com".
    return rule.include_subdomains and host.endswith("." + rule.value)


class RedirectGuard:
    """Validates a redirect chain hop by hop, with a hop budget.

    Create one guard per request chain: the hop counter is per instance.
    """

    def __init__(self, engine: ScopeEngine, *, max_hops: int = 5) -> None:
        self._engine = engine
        self._max_hops = max_hops
        self._hops = 0

    def follow(self, current_url: str, location: str) -> Decision:
        self._hops += 1
        if self._hops > self._max_hops:
            return _deny(DenyReason.too_many_redirects, hops=str(self._hops))
        try:
            target = urljoin(current_url, location)
        except ValueError:
            return _deny(DenyReason.invalid_target, message="malformed redirect location")
        return self._engine.evaluate_url(target)
