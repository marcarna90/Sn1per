"""Normalise the many ways tools spell severity into Jarvis' canonical set."""

from __future__ import annotations

from jarvis.report.model import SEVERITY_ORDER

# Map common aliases emitted by nuclei, sc0pe, Nessus, OpenVAS, etc. onto the
# canonical labels in SEVERITY_ORDER.
_ALIASES = {
    "critical": "critical",
    "crit": "critical",
    "high": "high",
    "important": "high",
    "medium": "medium",
    "med": "medium",
    "moderate": "medium",
    "low": "low",
    "info": "info",
    "informational": "info",
    "information": "info",
    "unknown": "info",
    "none": "info",
}


def normalize(raw: str) -> str:
    """Return a canonical severity label for an arbitrary input string.

    Falls back to ``info`` for anything unrecognised so a weird label never
    silently drops a finding out of the report.
    """
    if not raw:
        return "info"
    key = raw.strip().lower()
    if key in _ALIASES:
        return _ALIASES[key]
    for canon in SEVERITY_ORDER:
        if canon in key:
            return canon
    return "info"
