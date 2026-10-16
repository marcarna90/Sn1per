"""TLS/certificate exposure checks.

Pure evaluators (given a cert expiry date or a negotiated protocol) are
testable offline. Live fetching uses the standard-library ``ssl`` module only
(no third-party dependency) and is opt-in.
"""

from __future__ import annotations

import socket
import ssl
from datetime import datetime, timezone

from jarvis.asm.model import AttackSurface, AssetKind, Exposure

# Ports commonly wrapped in TLS.
TLS_PORTS = {443, 465, 563, 636, 853, 989, 990, 993, 995, 8443, 9443}

# Protocols considered deprecated/weak.
_WEAK_PROTOCOLS = {"sslv2", "sslv3", "tlsv1", "tlsv1.0", "tlsv1.1"}

_NEAR_EXPIRY_DAYS = 21


def cert_expiry_exposure(host: str, not_after: datetime, now: datetime | None = None) -> Exposure | None:
    """Flag an expired or soon-to-expire certificate."""
    now = now or datetime.now(timezone.utc)
    if not_after.tzinfo is None:
        not_after = not_after.replace(tzinfo=timezone.utc)
    days = (not_after - now).days
    if days < 0:
        return Exposure(
            category="weak_tls",
            title="Expired TLS certificate",
            severity="high",
            asset=host,
            detail=f"Certificate expired {abs(days)} day(s) ago ({not_after.date()}).",
            remediation="Renew and deploy a valid certificate; automate renewal (e.g. ACME).",
            source="asm:tls",
        )
    if days <= _NEAR_EXPIRY_DAYS:
        return Exposure(
            category="weak_tls",
            title="TLS certificate expiring soon",
            severity="low",
            asset=host,
            detail=f"Certificate expires in {days} day(s) ({not_after.date()}).",
            remediation="Renew the certificate before expiry; automate renewal.",
            source="asm:tls",
        )
    return None


def protocol_exposure(host: str, protocol: str) -> Exposure | None:
    """Flag a deprecated TLS/SSL protocol version."""
    if protocol.strip().lower().replace(" ", "") in _WEAK_PROTOCOLS:
        return Exposure(
            category="weak_tls",
            title=f"Deprecated TLS protocol ({protocol})",
            severity="medium",
            asset=host,
            detail=f"{host} negotiates {protocol}, which is deprecated.",
            remediation="Disable SSLv2/SSLv3/TLS1.0/1.1; require TLS 1.2+ with strong ciphers.",
            source="asm:tls",
        )
    return None


def _fetch_cert_not_after(host: str, port: int, timeout: int = 6) -> datetime | None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
    except (OSError, ssl.SSLError, ValueError):
        return None
    if not cert or "notAfter" not in cert:
        return None
    try:
        # e.g. 'Jun  1 12:00:00 2026 GMT'
        dt = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z")
        return dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def enrich_tls(surface: AttackSurface, live: bool = False) -> int:
    """Append TLS exposures for TLS-bearing services. Live fetch is opt-in."""
    if not live:
        return 0
    added = 0
    checked: set[str] = set()
    for asset in surface.assets:
        if asset.kind != AssetKind.SERVICE.value:
            continue
        port = asset.attributes.get("port")
        if port not in TLS_PORTS:
            continue
        host = asset.parent
        key = f"{host}:{port}"
        if not host or key in checked:
            continue
        checked.add(key)
        not_after = _fetch_cert_not_after(host, int(port))
        if not_after is None:
            continue
        exp = cert_expiry_exposure(key, not_after)
        if exp:
            surface.exposures.append(exp)
            added += 1
    return added
