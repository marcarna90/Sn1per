"""Attach actionable remediation guidance to findings.

Matching is intentionally simple and transparent: a set of keyword rules
checked against the finding name/location, with a severity-based fallback so
*every* finding carries at least some guidance. This is advisory text to help
a reader act on the report — it is not a substitute for analyst judgement.
"""

from __future__ import annotations

# (keywords, guidance). Keywords are alternatives: the first rule with ANY
# keyword present in the finding text wins, so order rules most-specific first.
_RULES: list[tuple[tuple[str, ...], str]] = [
    (("log4j", "log4shell"),
     "Upgrade Log4j to 2.17.1+ (or patched vendor build); remove the JndiLookup class if upgrade is blocked, and block outbound LDAP/RMI."),
    (("rce", "remote code execution", "command execution"),
     "Patch the affected component to a fixed version and restrict/inspect the input path; isolate the host until remediated."),
    (("sql injection", "sqli"),
     "Use parameterised queries/prepared statements, validate input, and apply least-privilege to the DB account."),
    (("xss", "cross-site scripting"),
     "Context-encode output, apply a strict Content-Security-Policy, and validate/escape user input."),
    (("ssrf",),
     "Validate and allow-list outbound request destinations; block link-local/metadata ranges; disable unused URL schemes."),
    (("directory traversal", "path traversal", "lfi", "file read"),
     "Canonicalise and allow-list file paths; run the service with least privilege; patch the affected component."),
    (("heartbleed", "openssl"),
     "Upgrade OpenSSL to a fixed release, reissue and rotate affected certificates/keys, and force credential resets."),
    (("security header", "content-security-policy", "x-frame-options", "hsts"),
     "Add the missing HTTP security headers (CSP, X-Frame-Options/ frame-ancestors, HSTS, X-Content-Type-Options) at the web server or app layer."),
    (("open relay",),
     "Reconfigure the MTA to reject unauthenticated relay; restrict relaying to authenticated senders and known networks."),
    (("mysql", "mssql", "database", "mongodb", "redis", "postgres"),
     "Do not expose database services to untrusted networks; bind to localhost/VPN, enforce authentication and TLS, and firewall the port."),
    (("smb signing",),
     "Enforce SMB signing on servers and clients via policy to prevent relay/MITM."),
    (("trace method",),
     "Disable the HTTP TRACE/TRACK methods at the web server."),
    (("weak", "mac algorithm", "cipher", "ssl", "tls"),
     "Disable weak ciphers/MACs/protocol versions and prefer modern TLS (1.2+/1.3) with strong suites."),
    (("version disclosure", "banner", "discloses", "tech-detect", "server:"),
     "Suppress version/banner disclosure where possible to reduce fingerprinting; keep the software patched."),
    (("exposed", ".git", "backup", "robots"),
     "Remove the exposed resource from the web root or restrict access; review for leaked secrets and rotate as needed."),
    (("default", "account", "credential", "login"),
     "Change default credentials, enforce strong unique passwords/MFA, and restrict administrative interfaces."),
]

_FALLBACK = {
    "critical": "Treat as an immediate priority: validate exploitability, patch or isolate the affected asset, and investigate for compromise.",
    "high": "Prioritise remediation: patch/harden the affected component and restrict exposure.",
    "medium": "Plan remediation in the normal cycle: patch or reconfigure to reduce exposure.",
    "low": "Address opportunistically as part of routine hardening.",
    "info": "Informational: review for context; no direct action usually required.",
}


def suggest(name: str, location: str = "", severity: str = "info") -> str:
    """Return remediation guidance for a finding."""
    haystack = f"{name} {location}".lower()
    for keywords, guidance in _RULES:
        if any(kw in haystack for kw in keywords):
            return guidance
    return _FALLBACK.get(severity, _FALLBACK["info"])
