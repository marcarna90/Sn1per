"""Jarvis - orchestration & reporting layer for the Sn1per Community engine.

Jarvis is intentionally dependency-light: the reporting engine runs on the
Python 3 standard library alone, so ``jarvis report`` works on any box that
can run Sn1per without a single ``pip install``. Optional features (PDF
export) degrade gracefully when their external helpers are absent.
"""

from jarvis.branding import VERSION

__version__ = VERSION
__all__ = ["__version__"]
