# ADR 0004 — Scope engine: allowlist, hard-denied ranges, DNS pinning, re-validation

Status: Accepted

## Context

The platform must never scan outside an explicitly authorised perimeter. The
audited legacy tool only had a regex *exclusion* list on the target name, with no
CIDR validation, no DNS/redirect checks and no allowlist. SSRF through the
orchestrator itself (internal services, cloud metadata) is the main threat.

## Decision

`neo_orchestro.scope` is a **pure policy package** (no DB, no network except an
injected `Resolver`). Its contract:

1. **Default deny.** A target runs only if a rule of the organisation authorises
   it. Rules are `domain` (optionally with subdomains, matched on a **dot
   boundary** so `notexample.com` ≠ `example.com`), `ip`, or `cidr`.
2. **Internal and external are separate authorisations.** Public addresses need an
   `external` rule; private/ULA/CGNAT addresses need an explicit `internal` IP/CIDR
   rule — a domain rule never implicitly authorises private answers (this is what
   stops DNS rebinding to internal hosts). The engine re-derives the class from the
   address and ignores a stored class that disagrees.
3. **Hard-denied classes are never scannable**, whatever the rules: loopback,
   link-local (incl. `169.254.169.254`), unspecified, multicast, reserved
   (240/4, broadcast), and metadata endpoints outside link-local
   (`fd00:ec2::254`, `100.100.100.200`, `192.0.0.192`). Classification looks through
   IPv4-mapped IPv6, 6to4 and NAT64 so a denied IPv4 cannot hide in IPv6 dress.
4. **Strict parsing.** Targets are a domain or an IP literal, nothing else: no URL,
   port, userinfo, wildcard, whitespace/control/format characters (incl. RTL
   override), percent-encoding, IPv6 zone ids. Numeric-looking hosts that are not a
   canonical dotted quad (`2130706433`, `0x7f.1`, `127.1`, `0177.0.0.1`) are refused
   because OS resolvers read them as IP addresses (classic SSRF bypass).
5. **No DNS for unauthorised input.** Malformed or out-of-scope names are refused
   before any lookup (no data exfiltration through DNS queries).
6. **Validate every answer, then pin.** All A/AAAA answers must pass; the validated
   set is returned as `Decision.pinned_ips`, empty on denial. Executors must connect
   to pinned IPs rather than re-resolving. DNS failures, empty answers, non-IP
   answers and more than 16 addresses all **fail closed**.
7. **Re-validate at execution.** The API checks at request time; the **worker checks
   again** immediately before running (fresh DNS), so rules changed or DNS rebinding
   between the two are caught. The decision snapshot is stored on the scan
   (`scans.scope_decision`) and in the audit log.
8. **Redirects are untrusted input.** `RedirectGuard` re-evaluates every hop (scheme
   http/https only, no userinfo, host re-resolved and re-classified) under a hop
   budget. HTTP engines must disable their client's automatic redirect following and
   use the guard.
9. **Rule creation is validated** (`build_rule`): normalisation, bare addresses are not
   CIDRs, host bits rejected, minimum prefix `/16` (v4) and `/48` (v6) by default
   (configurable), refusal of ranges overlapping hard-denied space or mixing public
   and private space.

Verified by 192 unit/security tests, plus a mutation check in which each of eight
safeguards was deliberately disabled and the suite failed every time.

## Known limits (open, tracked)

- **No public-suffix list.** `*.co.uk`-style entries (`co.uk` + subdomains) pass the
  two-label rule. Mitigations today: admin-only, audited. Follow-up: validate against
  the Public Suffix List (new dependency + data licence review).
- IDNA uses Python's IDNA-2003 codec; IDNA-2008 edge cases (e.g. `ß`) may differ.
- DNS answers are trusted as returned by the configured resolver (no DNSSEC). Point
  workers at a trusted resolver.
- A residual TOCTOU remains between final validation and the tool's connect **unless
  the executor uses `pinned_ips`**. Engine adapters (Phase 3+) must pass the pinned IP
  to the tool, not the host name (Host/SNI can be supplied separately).
- Ports and protocols are not part of scope yet (a future dimension).

## Alternatives rejected

- *Blacklist only (legacy behaviour)* — fails open on anything not listed.
- *Validate at API time only* — vulnerable to TOCTOU/rebinding and rule changes.
- *Let the tool resolve the name* — it would see answers we never validated.
