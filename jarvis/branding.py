"""Central branding for the Jarvis orchestration & reporting layer.

This is the *only* file you need to edit to rebrand the add-on. Every
report, banner and output label reads its identity from here, so changing
the values below propagates everywhere (HTML/Markdown/JSON reports, the CLI
banner, PDF metadata, etc.).

Jarvis is a thin, self-contained layer that sits on top of the Sn1per
Community engine. It does not replace Sn1per: it consumes the loot that
Sn1per produces and turns it into presentable, portable deliverables.
"""

# --- Identity -------------------------------------------------------------
NAME = "Jarvis"
LONG_NAME = "Jarvis Orchestration & Reporting Layer"
TAGLINE = "Ethical hacking orchestration & reporting for Sn1per"
# Shown in report footers / "powered by" lines. Keep the Sn1per credit:
# Jarvis orchestrates Sn1per, it is not a replacement for it.
ENGINE_CREDIT = "Built on the Sn1per Community engine"
VERSION = "0.1.0"

# --- Palette (used by the HTML renderer; both light & dark aware) ---------
# Single accent colour drives the theme. Change this to re-skin the report.
COLOR_ACCENT = "#36c5f0"
COLOR_ACCENT_DARK = "#0b6fa4"

# Severity colours follow the common CVSS-style convention. Override freely.
SEVERITY_COLORS = {
    "critical": "#b4237a",
    "high": "#e11d48",
    "medium": "#f59e0b",
    "low": "#3b82f6",
    "info": "#64748b",
}
