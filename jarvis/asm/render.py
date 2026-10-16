"""Render an :class:`AttackSurface` to client-ready reports.

Two HTML layouts share one stylesheet:

* **technical** - full asset inventory + every exposure grouped by category.
* **executive** - a one-page posture summary (big grade, per-category bars,
  top risks, asset counts) for a non-technical audience.
"""

from __future__ import annotations

import json
from html import escape

from jarvis import branding
from jarvis.asm.model import AttackSurface, AssetKind, category_label
from jarvis.report.model import SEVERITY_ORDER

_GRADE_COLORS = {
    "A": "#16a34a", "B": "#0ea5a4", "C": "#f59e0b", "D": "#f97316", "F": "#e11d48",
}


def _grade_color(letter: str) -> str:
    return _GRADE_COLORS.get(letter, "#64748b")


# --------------------------------------------------------------------------
# JSON / Markdown
# --------------------------------------------------------------------------
def render_json(asm: AttackSurface) -> str:
    return json.dumps(
        {
            "tool": {"name": branding.NAME, "version": branding.VERSION, "report": "asm"},
            "attack_surface": asm.to_dict(),
        },
        indent=2,
        ensure_ascii=False,
    )


def render_markdown(asm: AttackSurface) -> str:
    posture = asm.posture()
    counts = asm.severity_counts()
    acounts = asm.asset_counts()
    out: list[str] = []
    a = out.append
    a(f"# {branding.NAME} — Attack Surface Report")
    a("")
    if asm.client:
        a(f"**Client:** {asm.client}  ")
    a(f"**Engagement:** {asm.name}  ")
    a(f"**Generated:** {asm.generated_at}  ")
    a(f"**Posture grade:** {posture['grade']} — {posture['rating']} "
      f"(score {posture['score']}/100)")
    a("")
    a("## Attack surface summary")
    a("")
    a(f"- Assets discovered: **{len(asm.assets)}**")
    for kind, n in acounts.items():
        if n:
            a(f"  - {kind}: {n}")
    a(f"- Exposures: **{len(asm.exposures)}** "
      f"({', '.join(f'{counts[s]} {s}' for s in SEVERITY_ORDER if counts[s]) or 'none'})")
    a("")
    a("## Posture by category")
    a("")
    a("| Category | Grade | Exposures |")
    a("| --- | --- | --- |")
    for cat, info in sorted(
        posture["per_category"].items(), key=lambda kv: -kv[1]["count"]
    ):
        a(f"| {info['label']} | {info['grade']} | {info['count']} |")
    a("")
    a("## Exposures")
    a("")
    if asm.exposures:
        a("| Severity | Category | Finding | Asset | Remediation |")
        a("| --- | --- | --- | --- | --- |")
        for e in asm.exposures_sorted():
            def esc(x: str) -> str:
                return (x or "").replace("|", "\\|").replace("\n", " ")
            a(f"| {e.severity.capitalize()} | {esc(category_label(e.category))} | "
              f"{esc(e.title)} | {esc(e.asset)} | {esc(e.remediation)} |")
    else:
        a("_No exposures identified._")
    a("")
    a("---")
    a(f"_{branding.LONG_NAME} v{branding.VERSION} · {branding.ENGINE_CREDIT}._")
    a("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# HTML
# --------------------------------------------------------------------------
def _css() -> str:
    accent = branding.COLOR_ACCENT
    accent_dark = branding.COLOR_ACCENT_DARK
    return f"""
:root {{ --accent:{accent}; --bg:#f6f8fb; --card:#fff; --ink:#0f172a;
  --muted:#64748b; --line:#e2e8f0; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{
  --accent:{accent_dark}; --bg:#0b1220; --card:#111a2e; --ink:#e8eef9;
  --muted:#94a3b8; --line:#22304a; }} }}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:32px 16px 64px}}
header.r{{display:flex;flex-wrap:wrap;gap:16px;justify-content:space-between;
  align-items:center;border-bottom:3px solid var(--accent);padding-bottom:18px;margin-bottom:26px}}
.brand{{font-size:24px;font-weight:800;letter-spacing:-.5px}}
.brand span{{color:var(--accent)}}
.brand small{{display:block;font-size:12px;font-weight:500;color:var(--muted)}}
.meta{{text-align:right;font-size:13px;color:var(--muted)}}
.grade{{display:flex;align-items:center;gap:18px;background:var(--card);
  border:1px solid var(--line);border-radius:14px;padding:22px;margin-bottom:22px}}
.gcircle{{width:96px;height:96px;border-radius:50%;display:flex;align-items:center;
  justify-content:center;font-size:46px;font-weight:800;color:#fff;flex:0 0 auto}}
.gtext b{{font-size:19px}}
.kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px}}
.kpi{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}}
.kpi .v{{font-size:28px;font-weight:800;line-height:1}}
.kpi .l{{color:var(--muted);font-size:12.5px;margin-top:6px}}
section{{background:var(--card);border:1px solid var(--line);border-radius:12px;
  padding:22px;margin-bottom:20px}}
h2{{margin:0 0 14px;font-size:18px}} h3{{margin:18px 0 8px;font-size:15px}}
table{{width:100%;border-collapse:collapse;font-size:13.5px}}
th{{text-align:left;color:var(--muted);border-bottom:2px solid var(--line);padding:7px 9px}}
td{{border-bottom:1px solid var(--line);padding:7px 9px;vertical-align:top}}
.badge{{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:700}}
.mono{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px;word-break:break-word}}
.catbar{{display:grid;grid-template-columns:200px 1fr 54px;gap:10px;align-items:center;margin:7px 0}}
.track{{background:var(--line);border-radius:999px;height:12px;overflow:hidden}}
.fill{{height:100%;border-radius:999px}}
.muted{{color:var(--muted)}} .rem{{color:var(--muted);font-size:12.5px;margin-top:4px;font-style:italic}}
ul.cols{{columns:3;list-style:none;padding:0;margin:8px 0 0;font-size:12.5px}}
ul.cols li{{padding:1px 0;break-inside:avoid}}
summary{{cursor:pointer;font-weight:600;margin-top:8px}}
code{{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12px}}
footer{{color:var(--muted);font-size:12px;text-align:center;margin-top:26px}}
@media(max-width:720px){{.kpis{{grid-template-columns:repeat(2,1fr)}}.catbar{{grid-template-columns:120px 1fr 44px}}}}
@media print{{body{{background:#fff}}section,.kpi,.grade{{break-inside:avoid}}}}
"""


def _sev_badge(sev: str) -> str:
    color = branding.SEVERITY_COLORS.get(sev, "#64748b")
    return (f'<span class="badge" style="background:{color}1a;color:{color};'
            f'border:1px solid {color}66">{escape(sev.capitalize())}</span>')


def _header(asm: AttackSurface, subtitle: str) -> str:
    client = f'<br>Client: <b style="color:var(--ink)">{escape(asm.client)}</b>' if asm.client else ""
    return f"""<header class="r">
  <div class="brand">{escape(branding.NAME)}<span>.</span>
    <small>{escape(subtitle)}</small></div>
  <div class="meta">Engagement: {escape(asm.name)}<br>
    Generated: {escape(asm.generated_at)}{client}</div>
</header>"""


def _grade_block(asm: AttackSurface) -> str:
    p = asm.posture()
    color = _grade_color(p["grade"])
    return f"""<div class="grade">
  <div class="gcircle" style="background:{color}">{escape(p['grade'])}</div>
  <div class="gtext"><b>Attack surface posture: {escape(p['rating'])}</b><br>
    <span class="muted">Score {p['score']}/100 · {len(asm.assets)} assets ·
    {len(asm.exposures)} exposures</span></div>
</div>"""


def _kpis(asm: AttackSurface) -> str:
    c = asm.severity_counts()
    urgent = c["critical"] + c["high"]
    cells = [
        (len(asm.assets), "Assets"),
        (len(asm.exposures), "Exposures"),
        (urgent, "Critical + High"),
        (asm.asset_counts().get(AssetKind.SUBDOMAIN.value, 0), "Subdomains"),
    ]
    return '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{escape(l)}</div></div>'
        for v, l in cells
    ) + "</div>"


def _category_bars(asm: AttackSurface) -> str:
    p = asm.posture()
    cats = sorted(p["per_category"].items(), key=lambda kv: -kv[1]["count"])
    rows = []
    for _cat, info in cats:
        pct = max(4, min(100, info["count"] * 12))
        color = _grade_color(info["grade"])
        rows.append(
            f'<div class="catbar"><div>{escape(info["label"])}</div>'
            f'<div class="track"><div class="fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<div style="text-align:right"><b style="color:{color}">{escape(info["grade"])}</b> '
            f'<span class="muted">({info["count"]})</span></div></div>'
        )
    return "\n".join(rows) or '<p class="muted">No exposures.</p>'


def _top_risks(asm: AttackSurface, limit: int = 5) -> str:
    rows = []
    for e in asm.exposures_sorted()[:limit]:
        rows.append(
            f"<tr><td>{_sev_badge(e.severity)}</td><td>{escape(e.title)}"
            f'<div class="rem">&#8617; {escape(e.remediation)}</div></td>'
            f'<td class="mono">{escape(e.asset) or "&mdash;"}</td></tr>'
        )
    if not rows:
        return '<p class="muted">No exposures identified.</p>'
    return ('<table><thead><tr><th>Severity</th><th>Top risk</th><th>Asset</th>'
            "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def _inventory(asm: AttackSurface) -> str:
    by_kind = asm.assets_by_kind()
    blocks = []
    for kind in AssetKind:
        items = by_kind.get(kind.value, [])
        if not items:
            continue
        rows = "".join(
            f'<tr><td class="mono">{escape(a.value)}</td>'
            f'<td class="mono muted">{escape(a.parent)}</td>'
            f'<td class="muted">{escape(a.source)}</td></tr>'
            for a in items[:500]
        )
        blocks.append(
            f"<h3>{escape(kind.value)} ({len(items)})</h3>"
            "<table><thead><tr><th>Asset</th><th>Parent</th><th>Source</th></tr>"
            f"</thead><tbody>{rows}</tbody></table>"
        )
    return "\n".join(blocks) or '<p class="muted">No assets discovered.</p>'


def _exposures_by_cat(asm: AttackSurface) -> str:
    grouped = asm.exposures_by_category()
    rank = {s: i for i, s in enumerate(SEVERITY_ORDER)}
    blocks = []
    order = sorted(grouped.items(), key=lambda kv: -len(kv[1]))
    for cat, items in order:
        items = sorted(items, key=lambda e: rank.get(e.severity, 99))
        rows = "".join(
            f"<tr><td>{_sev_badge(e.severity)}</td><td>{escape(e.title)}"
            f'<div class="rem">&#8617; {escape(e.remediation)}</div></td>'
            f'<td class="mono">{escape(e.asset) or "&mdash;"}</td>'
            f'<td class="mono muted">{escape(e.detail)[:160] or "&mdash;"}</td></tr>'
            for e in items
        )
        blocks.append(
            f"<h3>{escape(category_label(cat))} ({len(items)})</h3>"
            "<table><thead><tr><th>Severity</th><th>Finding</th><th>Asset</th>"
            f"<th>Detail</th></tr></thead><tbody>{rows}</tbody></table>"
        )
    return "\n".join(blocks) or '<p class="muted">No exposures identified.</p>'


def _diff_section(asm: AttackSurface) -> str:
    d = asm.extras.get("diff")
    if not d:
        return ""
    posture = d.get("posture", {})
    delta = posture.get("score_delta", 0)
    if delta > 0:
        trend = f'<span style="color:#16a34a">improved +{delta}</span>'
    elif delta < 0:
        trend = f'<span style="color:{branding.SEVERITY_COLORS["high"]}">worsened {delta}</span>'
    else:
        trend = '<span class="muted">unchanged</span>'
    exp = d.get("exposures", {})
    ast = d.get("assets", {})

    def exp_list(items, label, color):
        if not items:
            return ""
        rows = "".join(
            f"<tr><td>{_sev_badge(i['severity'])}</td><td>{escape(i['title'])}</td>"
            f'<td class="mono">{escape(i["asset"]) or "&mdash;"}</td></tr>'
            for i in items[:50]
        )
        return (f'<h3 style="color:{color}">{escape(label)} ({len(items)})</h3>'
                "<table><thead><tr><th>Severity</th><th>Exposure</th><th>Asset</th>"
                f"</tr></thead><tbody>{rows}</tbody></table>")

    since = escape(d.get("previous_at", "")) or "previous scan"
    summary = (
        f'<p>Since <b>{since}</b>: posture {trend} '
        f'(score {posture.get("score_before", "?")} &rarr; {posture.get("score_after", "?")}'
        + (f', grade {escape(posture.get("grade_change",""))}' if posture.get("grade_change") else "")
        + f'). New assets: <b>{ast.get("added_count",0)}</b>, removed: '
        f'<b>{ast.get("removed_count",0)}</b>. New exposures: '
        f'<b>{exp.get("added_count",0)}</b>, resolved: <b>{exp.get("removed_count",0)}</b>.</p>'
    )
    return (
        '<section><h2>Changes since last scan</h2>' + summary
        + exp_list(exp.get("added", []), "New exposures", branding.SEVERITY_COLORS["high"])
        + exp_list(exp.get("removed", []), "Resolved exposures", "#16a34a")
        + "</section>"
    )


def _typosquat_section(asm: AttackSurface) -> str:
    data = asm.extras.get("typosquat")
    if not data:
        return ""
    registered = data.get("registered", [])
    watchlist = data.get("watchlist", {})
    total = sum(len(v) for v in watchlist.values())
    if not total:
        return ""
    reg_html = ""
    if registered:
        items = "".join(f'<li class="mono">{escape(d)}</li>' for d in registered)
        reg_html = (
            f'<h3 style="color:{branding.SEVERITY_COLORS["medium"]}">'
            f"Registered look-alikes ({len(registered)})</h3>"
            f'<ul class="cols">{items}</ul>'
        )
    elif data.get("checked_live"):
        reg_html = '<p class="muted">No generated look-alike currently resolves.</p>'
    else:
        reg_html = ('<p class="muted">Watchlist only — run with <code>--live</code> '
                    "to check which look-alikes are registered.</p>")

    blocks = []
    for apex, cands in sorted(watchlist.items()):
        lis = "".join(f'<li class="mono">{escape(c)}</li>' for c in cands)
        blocks.append(
            f"<details><summary>{escape(apex)} — {len(cands)} look-alikes</summary>"
            f'<ul class="cols">{lis}</ul></details>'
        )
    return (
        '<section><h2>Brand protection — look-alike domains</h2>'
        + reg_html + "".join(blocks) + "</section>"
    )


def _doc(title: str, body: str) -> str:
    return f"""<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<meta name="generator" content="{escape(branding.LONG_NAME)} v{branding.VERSION}">
<style>{_css()}</style></head><body><div class="wrap">{body}
<footer>{escape(branding.LONG_NAME)} v{branding.VERSION} &middot; {escape(branding.ENGINE_CREDIT)}<br>
For authorised security testing only.</footer>
</div></body></html>"""


def render_html(asm: AttackSurface, executive: bool = False) -> str:
    if executive:
        subtitle = "Attack Surface — Executive summary"
        body = (
            _header(asm, subtitle)
            + _grade_block(asm)
            + _kpis(asm)
            + _diff_section(asm)
            + '<section><h2>Posture by category</h2>' + _category_bars(asm) + "</section>"
            + '<section><h2>Top risks</h2>' + _top_risks(asm) + "</section>"
        )
        return _doc(f"{branding.NAME} ASM — {asm.name}", body)

    subtitle = "External Attack Surface Report"
    body = (
        _header(asm, subtitle)
        + _grade_block(asm)
        + _kpis(asm)
        + _diff_section(asm)
        + '<section><h2>Posture by category</h2>' + _category_bars(asm) + "</section>"
        + '<section><h2>Exposures</h2>' + _exposures_by_cat(asm) + "</section>"
        + _typosquat_section(asm)
        + '<section><h2>Asset inventory</h2>' + _inventory(asm) + "</section>"
    )
    return _doc(f"{branding.NAME} ASM — {asm.name}", body)
