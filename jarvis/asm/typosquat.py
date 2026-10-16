"""Brand-protection: generate and (optionally) resolve look-alike domains.

``generate_candidates`` is pure and deterministic, so the permutation logic is
fully testable. Registration/resolution is a separate, opt-in network step
using only the standard library (``socket``). Confirmed-registered look-alikes
become ``typosquat_domain`` exposures; the full candidate list is kept as a
watchlist in the report even without live checks.
"""

from __future__ import annotations

import socket

from jarvis.asm.model import AttackSurface, AssetKind, Exposure

# Minimal keyboard adjacency for replacement typos.
_KEYBOARD = {
    "a": "qsz", "b": "vgn", "c": "xdv", "d": "sfe", "e": "wrd", "f": "dgr",
    "g": "fht", "h": "gjy", "i": "uok", "j": "hkn", "k": "jlm", "l": "ko",
    "m": "nk", "n": "bm", "o": "ipl", "p": "ol", "q": "wa", "r": "et",
    "s": "adw", "t": "ry", "u": "yi", "v": "cb", "w": "qse", "x": "zc",
    "y": "tu", "z": "xs",
}
_HOMOGLYPHS = {"o": "0", "l": "1", "i": "1", "e": "3", "s": "5", "a": "4", "b": "8"}
_ALT_TLDS = ["com", "net", "org", "co", "io", "info", "biz", "online", "site", "xyz"]
_AFFIXES = ["secure", "login", "account", "mail", "support", "www", "my"]


def _apex(domain: str) -> str:
    """Reduce to the registrable apex (last two labels). ccTLD-naive but fine."""
    parts = [p for p in domain.strip().lower().split(".") if p]
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.strip().lower()


def generate_candidates(domain: str, max_candidates: int = 60) -> list[str]:
    """Return deterministic look-alike domains for a domain's apex."""
    apex = _apex(domain)
    sld, _, tld = apex.rpartition(".")
    if not sld:
        return []

    out: list[str] = []
    seen: set[str] = {apex}

    def add(new_sld: str, new_tld: str = tld) -> None:
        cand = f"{new_sld}.{new_tld}"
        if new_sld and cand not in seen:
            seen.add(cand)
            out.append(cand)

    n = len(sld)
    # omission
    for i in range(n):
        add(sld[:i] + sld[i + 1:])
    # repetition
    for i in range(n):
        add(sld[:i] + sld[i] + sld[i:])
    # transposition (adjacent swap)
    for i in range(n - 1):
        add(sld[:i] + sld[i + 1] + sld[i] + sld[i + 2:])
    # keyboard replacement
    for i, ch in enumerate(sld):
        for alt in _KEYBOARD.get(ch, ""):
            add(sld[:i] + alt + sld[i + 1:])
    # homoglyph substitution (one char at a time)
    for i, ch in enumerate(sld):
        if ch in _HOMOGLYPHS:
            add(sld[:i] + _HOMOGLYPHS[ch] + sld[i + 1:])
    # TLD swap
    for alt_tld in _ALT_TLDS:
        if alt_tld != tld:
            add(sld, alt_tld)
    # affixes
    for word in _AFFIXES:
        add(f"{word}-{sld}")
        add(f"{sld}-{word}")

    return out[:max_candidates]


def resolve(domain: str, timeout: float = 3.0) -> bool:
    """Return True if the domain resolves (best-effort; never raises)."""
    old = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        socket.gethostbyname(domain)
        return True
    except (OSError, UnicodeError, ValueError):
        return False
    finally:
        socket.setdefaulttimeout(old)


def enrich_typosquat(
    surface: AttackSurface, live: bool = False, max_candidates: int = 40
) -> int:
    """Generate look-alike domains for the surface's apex domains.

    Always records a watchlist in ``surface.extras['typosquat']``. When
    ``live`` is set, candidates that resolve become typosquat_domain exposures.
    Returns the number of exposures added.
    """
    apexes = sorted({
        _apex(a.value)
        for a in surface.assets
        if a.kind in (AssetKind.DOMAIN.value, AssetKind.SUBDOMAIN.value,
                      AssetKind.EMAIL_DOMAIN.value)
    })
    watchlist: dict[str, list[str]] = {}
    registered: list[str] = []
    added = 0
    for apex in apexes:
        candidates = generate_candidates(apex, max_candidates=max_candidates)
        watchlist[apex] = candidates
        if not live:
            continue
        for cand in candidates:
            if resolve(cand):
                registered.append(cand)
                surface.exposures.append(
                    Exposure(
                        category="typosquat_domain",
                        title=f"Registered look-alike domain of {apex}",
                        severity="medium",
                        asset=cand,
                        detail=f"{cand} resolves and closely resembles {apex}.",
                        remediation="Investigate ownership; consider defensive registration, takedown, and brand monitoring.",
                        source="asm:brand",
                    )
                )
                added += 1
    surface.extras["typosquat"] = {
        "watchlist": watchlist,
        "registered": registered,
        "checked_live": live,
    }
    return added
