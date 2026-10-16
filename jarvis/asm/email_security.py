"""Email-authentication exposure checks (SPF / DMARC / DKIM).

The analysis functions are pure (given the TXT records) so they test without a
network. Records are sourced two ways:

* **offline** - scanned from the loot directory (Sn1per's OSINT output and any
  captured DNS TXT data);
* **live** (opt-in) - queried with ``dig`` when available.

Findings become ``missing_email_security`` exposures on the attack surface.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from jarvis.asm.model import AttackSurface, AssetKind, Exposure


def analyze_spf(records: list[str]) -> Exposure | None:
    """Return an SPF exposure for a domain's TXT records, or None if fine."""
    spf = next((r for r in records if "v=spf1" in r.lower()), None)
    if spf is None:
        return Exposure(
            category="missing_email_security",
            title="No SPF record",
            severity="medium",
            detail="No v=spf1 TXT record found; the domain can be spoofed.",
            remediation="Publish an SPF record ending in -all that lists only authorised senders.",
            source="asm:email",
        )
    low = spf.lower()
    if "+all" in low:
        return Exposure(
            category="missing_email_security",
            title="Overly permissive SPF (+all)",
            severity="high",
            detail=f"SPF allows any sender: {spf}",
            remediation="Replace +all with -all and enumerate only legitimate senders.",
            source="asm:email",
        )
    if "?all" in low:
        return Exposure(
            category="missing_email_security",
            title="Neutral SPF (?all)",
            severity="low",
            detail=f"SPF neither passes nor fails unknown senders: {spf}",
            remediation="Tighten the SPF policy to -all once senders are confirmed.",
            source="asm:email",
        )
    return None  # ~all / -all are acceptable


def analyze_dmarc(records: list[str]) -> Exposure | None:
    dmarc = next((r for r in records if "v=dmarc1" in r.lower()), None)
    if dmarc is None:
        return Exposure(
            category="missing_email_security",
            title="No DMARC record",
            severity="medium",
            detail="No _dmarc v=DMARC1 record found; spoofing is unmonitored.",
            remediation="Publish a DMARC record; start at p=none for monitoring, then move to quarantine/reject.",
            source="asm:email",
        )
    m = re.search(r"p=(\w+)", dmarc.lower())
    policy = m.group(1) if m else ""
    if policy == "none":
        return Exposure(
            category="missing_email_security",
            title="Weak DMARC policy (p=none)",
            severity="low",
            detail=f"DMARC is monitoring-only: {dmarc}",
            remediation="Progress the DMARC policy to p=quarantine then p=reject.",
            source="asm:email",
        )
    return None


# --------------------------------------------------------------------------
# sourcing records
# --------------------------------------------------------------------------
def _records_from_loot(root: Path, domain: str) -> list[str]:
    """Best-effort: scrape TXT-looking SPF/DMARC strings for a domain from loot."""
    records: list[str] = []
    for sub in ("osint", "output", "nmap"):
        d = root / sub
        if not d.is_dir():
            continue
        for path in d.glob("*"):
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if domain.lower() not in text.lower() and "spf1" not in text.lower() \
                    and "dmarc1" not in text.lower():
                continue
            for line in text.splitlines():
                if "v=spf1" in line.lower() or "v=dmarc1" in line.lower():
                    records.append(line.strip())
    return records


def _query_txt_live(name: str) -> list[str]:
    dig = shutil.which("dig")
    if not dig:
        return []
    try:
        out = subprocess.run(
            [dig, "+short", "TXT", name],
            capture_output=True, text=True, timeout=10,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return []
    return [ln.strip().strip('"') for ln in out.splitlines() if ln.strip()]


def check_domain(domain: str, root: Path | None, live: bool) -> list[Exposure]:
    spf_records: list[str] = []
    dmarc_records: list[str] = []
    if root is not None:
        loot = _records_from_loot(root, domain)
        spf_records += loot
        dmarc_records += loot
    if live:
        spf_records += _query_txt_live(domain)
        dmarc_records += _query_txt_live(f"_dmarc.{domain}")

    exposures: list[Exposure] = []
    for analyzer, recs in ((analyze_spf, spf_records), (analyze_dmarc, dmarc_records)):
        # Only assert "missing" when we actually looked (live, or loot had data).
        looked = live or bool(recs)
        if not looked:
            continue
        exp = analyzer(recs)
        if exp:
            exp.asset = domain
            exposures.append(exp)
    return exposures


def enrich_email(surface: AttackSurface, root: Path | None = None, live: bool = False) -> int:
    """Append email-auth exposures for the surface's domains. Returns count added."""
    domains = {
        a.value.lower()
        for a in surface.assets
        if a.kind in (AssetKind.EMAIL_DOMAIN.value, AssetKind.DOMAIN.value)
    }
    added = 0
    for dom in sorted(domains):
        for exp in check_domain(dom, root, live):
            surface.exposures.append(exp)
            added += 1
    return added
