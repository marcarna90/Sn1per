"""Translate a campaign phase + target into a concrete ``sniper`` command.

This is the only module that encodes Sn1per's CLI surface, so adapting to a
new flag or mode is a localised change. Each orchestrated scan is run with
``--noreport`` because Jarvis produces the consolidated report at the end of
the campaign rather than one report per scan.
"""

from __future__ import annotations

from typing import Any

# Map campaign option keys onto sniper flags. Boolean options emit a bare
# flag when truthy; value options emit the flag followed by the value.
_BOOL_FLAGS = {
    "osint": "-o",
    "recon": "-re",
    "re": "-re",
    "bruteforce": "-b",
    "brute": "-b",
    "fullports": "-fp",
    "fullportonly": "-fp",
}
_VALUE_FLAGS = {
    "port": "-p",
    "config": "-c",
}


def build_sniper_command(
    target: str,
    mode: str,
    workspace: str,
    options: dict[str, Any] | None = None,
    sniper_bin: str = "sniper",
) -> list[str]:
    """Return the argv list for one orchestrated Sn1per scan."""
    options = options or {}
    cmd: list[str] = [sniper_bin, "-t", target, "-m", mode]
    if workspace:
        cmd += ["-w", workspace]

    for key, value in options.items():
        k = key.lower()
        if k in _BOOL_FLAGS:
            if value:
                cmd.append(_BOOL_FLAGS[k])
        elif k in _VALUE_FLAGS:
            if value not in (None, "", False):
                cmd += [_VALUE_FLAGS[k], str(value)]
        # Unknown options are ignored on purpose so a typo never injects
        # arbitrary arguments into the command line.

    # Jarvis owns the final report; suppress per-scan reporting.
    cmd.append("--noreport")
    return cmd
