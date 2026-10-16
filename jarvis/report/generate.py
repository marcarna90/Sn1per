"""Tie collection and rendering together into on-disk report files."""

from __future__ import annotations

import os
from pathlib import Path

from jarvis.report.collector import collect
from jarvis.report.model import Engagement
from jarvis.report.renderers import html as html_renderer
from jarvis.report.renderers import json_report as json_renderer
from jarvis.report.renderers import markdown as md_renderer

VALID_FORMATS = ("html", "md", "json", "pdf")


def _slug(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip("-")
    return safe or "report"


def generate_reports(
    loot_root: str | os.PathLike,
    out_dir: str | os.PathLike,
    formats: list[str] | None = None,
    name: str | None = None,
    engagement: Engagement | None = None,
) -> dict[str, str]:
    """Generate the requested report formats.

    Returns a mapping of format -> output path for everything that was
    produced. PDF is best-effort: if no backend is available it is skipped
    (with the reason recorded under the ``"pdf_error"`` key) rather than
    failing the whole run, since the HTML is always printable to PDF.
    """
    formats = [f.lower() for f in (formats or ["html", "md", "json"])]
    invalid = [f for f in formats if f not in VALID_FORMATS]
    if invalid:
        raise ValueError(
            f"Unknown format(s): {', '.join(invalid)}. "
            f"Valid formats: {', '.join(VALID_FORMATS)}"
        )

    if engagement is None:
        engagement = collect(loot_root, name=name)

    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = _slug(engagement.name)
    results: dict[str, str] = {}

    html_content = None
    if "html" in formats or "pdf" in formats:
        html_content = html_renderer.render(engagement)

    if "html" in formats:
        path = out / f"{base}-report.html"
        path.write_text(html_content, encoding="utf-8")
        results["html"] = str(path)

    if "md" in formats:
        path = out / f"{base}-report.md"
        path.write_text(md_renderer.render(engagement), encoding="utf-8")
        results["md"] = str(path)

    if "json" in formats:
        path = out / f"{base}-report.json"
        path.write_text(json_renderer.render(engagement), encoding="utf-8")
        results["json"] = str(path)

    if "pdf" in formats:
        from jarvis.report.renderers import pdf as pdf_renderer

        path = out / f"{base}-report.pdf"
        try:
            pdf_renderer.render_to_file(html_content, str(path))
            results["pdf"] = str(path)
        except pdf_renderer.PdfUnavailable as exc:
            results["pdf_error"] = str(exc)

    return results
