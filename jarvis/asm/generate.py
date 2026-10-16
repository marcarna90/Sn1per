"""Assemble and write Attack Surface Management reports."""

from __future__ import annotations

import os
from pathlib import Path

from jarvis.asm.build import build_attack_surface
from jarvis.asm.model import AttackSurface
from jarvis.asm import render
from jarvis.report.collector import collect
from jarvis.report.model import Engagement

VALID_FORMATS = ("html", "md", "json", "pdf")


def _slug(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in name).strip("-")
    return safe or "report"


def generate_asm_reports(
    loot_root: str | os.PathLike,
    out_dir: str | os.PathLike,
    formats: list[str] | None = None,
    name: str | None = None,
    client: str = "",
    executive: bool = True,
    live: bool = False,
    diff: bool = False,
    snapshot: bool = True,
    snapshot_base: str | os.PathLike | None = None,
    engagement: Engagement | None = None,
    surface: AttackSurface | None = None,
) -> dict[str, str]:
    """Generate ASM reports. Returns a mapping of output key -> path.

    Keys: ``html`` (technical), ``html_exec`` (one-pager, when ``executive``),
    ``md``, ``json``, ``pdf``, ``pdf_exec`` — plus ``pdf_error`` on PDF failure.
    """
    formats = [f.lower() for f in (formats or ["html", "md", "json"])]
    invalid = [f for f in formats if f not in VALID_FORMATS]
    if invalid:
        raise ValueError(
            f"Unknown format(s): {', '.join(invalid)}. Valid: {', '.join(VALID_FORMATS)}"
        )

    if surface is None:
        if engagement is None:
            engagement = collect(loot_root, name=name)
        surface = build_attack_surface(engagement, client=client)
        # Email-auth and TLS enrichment: offline from loot always, live opt-in.
        from jarvis.asm.email_security import enrich_email
        from jarvis.asm.tls import enrich_tls
        from jarvis.asm.typosquat import enrich_typosquat

        loot_path = Path(loot_root) if loot_root else None
        enrich_email(surface, root=loot_path, live=live)
        enrich_tls(surface, live=live)
        enrich_typosquat(surface, live=live)

    # Change tracking: diff against the most recent prior snapshot, then
    # persist the current one so trends accumulate across scans.
    snap_base = snapshot_base or loot_root
    if snap_base is not None:
        from jarvis.asm import diff as diffmod

        if diff:
            prev_path = diffmod.latest_snapshot(snap_base)
            if prev_path:
                try:
                    surface.extras["diff"] = diffmod.diff_surfaces(
                        diffmod.load_snapshot(prev_path), surface.to_dict()
                    )
                except (OSError, ValueError):
                    pass
        if snapshot:
            try:
                diffmod.save_snapshot(surface, snap_base)
            except OSError:
                pass

    out = Path(out_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    base = _slug(surface.name)
    results: dict[str, str] = {}

    html_tech = html_exec = None
    if "html" in formats or "pdf" in formats:
        html_tech = render.render_html(surface, executive=False)
        if executive:
            html_exec = render.render_html(surface, executive=True)

    if "html" in formats:
        p = out / f"{base}-attack-surface.html"
        p.write_text(html_tech, encoding="utf-8")
        results["html"] = str(p)
        if executive and html_exec is not None:
            pe = out / f"{base}-attack-surface-exec.html"
            pe.write_text(html_exec, encoding="utf-8")
            results["html_exec"] = str(pe)

    if "md" in formats:
        p = out / f"{base}-attack-surface.md"
        p.write_text(render.render_markdown(surface), encoding="utf-8")
        results["md"] = str(p)

    if "json" in formats:
        p = out / f"{base}-attack-surface.json"
        p.write_text(render.render_json(surface), encoding="utf-8")
        results["json"] = str(p)

    if "pdf" in formats:
        from jarvis.report.renderers import pdf as pdf_renderer

        try:
            p = out / f"{base}-attack-surface.pdf"
            pdf_renderer.render_to_file(html_tech, str(p))
            results["pdf"] = str(p)
            if executive and html_exec is not None:
                pe = out / f"{base}-attack-surface-exec.pdf"
                pdf_renderer.render_to_file(html_exec, str(pe))
                results["pdf_exec"] = str(pe)
        except pdf_renderer.PdfUnavailable as exc:
            results["pdf_error"] = str(exc)

    return results
