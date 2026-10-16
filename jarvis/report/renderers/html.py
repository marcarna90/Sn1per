"""Render an engagement to a single self-contained HTML report.

No external assets: all CSS is inlined and there is no JavaScript required to
read the report, so the file renders identically offline, in an email client
preview, or when printed to PDF from a browser. It is light/dark aware and
print-friendly.
"""

from __future__ import annotations

from html import escape

from jarvis import branding
from jarvis.report.model import SEVERITY_ORDER, Engagement


def _sev_badge(sev: str) -> str:
    color = branding.SEVERITY_COLORS.get(sev, "#64748b")
    label = escape(sev.capitalize())
    return (
        f'<span class="badge" style="background:{color}1a;color:{color};'
        f'border:1px solid {color}66">{label}</span>'
    )


def _kpi(value: object, label: str, accent: bool = False) -> str:
    cls = "kpi accent" if accent else "kpi"
    return (
        f'<div class="{cls}"><div class="kpi-value">{escape(str(value))}</div>'
        f'<div class="kpi-label">{escape(label)}</div></div>'
    )


def _severity_bars(engagement: Engagement) -> str:
    counts = engagement.severity_counts()
    total = max(1, len(engagement.vulnerabilities))
    rows = []
    for sev in SEVERITY_ORDER:
        n = counts[sev]
        pct = round(n / total * 100)
        color = branding.SEVERITY_COLORS.get(sev, "#64748b")
        rows.append(
            f'<div class="bar-row">'
            f'<div class="bar-label">{escape(sev.capitalize())}</div>'
            f'<div class="bar-track"><div class="bar-fill" '
            f'style="width:{pct}%;background:{color}"></div></div>'
            f'<div class="bar-count">{n}</div></div>'
        )
    return "\n".join(rows)


def _findings_table(engagement: Engagement) -> str:
    if not engagement.vulnerabilities:
        return '<p class="muted">No vulnerabilities were parsed from the loot directory.</p>'
    rows = []
    for v in engagement.vulnerabilities_sorted():
        loc = escape(v.location) or "&mdash;"
        ev = escape(v.evidence) or "&mdash;"
        rows.append(
            f"<tr><td>{_sev_badge(v.severity)}</td>"
            f"<td>{escape(v.name)}</td>"
            f'<td class="mono wrap">{loc}</td>'
            f'<td class="mono wrap">{ev}</td>'
            f'<td class="src">{escape(v.source)}</td></tr>'
        )
    return (
        '<table class="data"><thead><tr><th>Severity</th><th>Finding</th>'
        "<th>Location</th><th>Evidence</th><th>Source</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _hosts_section(engagement: Engagement) -> str:
    if not engagement.hosts:
        return '<p class="muted">No hosts were parsed from the loot directory.</p>'
    blocks = []
    for host in engagement.hosts:
        title = escape(host.target or host.ip or "unknown")
        meta = []
        if host.ip and host.ip != (host.target or ""):
            meta.append(f'IP <span class="mono">{escape(host.ip)}</span>')
        if host.os:
            meta.append(f"OS {escape(host.os)}")
        if host.mac:
            meta.append(f'MAC <span class="mono">{escape(host.mac)}</span>')
        meta.append(f"{len(host.open_ports)} open port(s)")
        meta_html = " &middot; ".join(meta)

        if host.open_ports:
            prows = "".join(
                f"<tr><td class='mono'>{p.number}/{escape(p.protocol)}</td>"
                f"<td>{escape(p.service) or '&mdash;'}</td>"
                f"<td>{escape(p.service_banner) or '&mdash;'}</td></tr>"
                for p in sorted(host.open_ports, key=lambda x: x.number)
            )
            ports_html = (
                '<table class="data"><thead><tr><th>Port</th><th>Service</th>'
                "<th>Details</th></tr></thead><tbody>" + prows + "</tbody></table>"
            )
        else:
            ports_html = '<p class="muted">No open ports recorded.</p>'

        blocks.append(
            f'<div class="host"><h3>{title}</h3>'
            f'<div class="host-meta">{meta_html}</div>{ports_html}</div>'
        )
    return "\n".join(blocks)


def _subdomains_section(engagement: Engagement) -> str:
    if not engagement.subdomains:
        return ""
    items = "".join(
        f"<li class='mono'>{escape(s)}</li>" for s in engagement.subdomains[:500]
    )
    extra = ""
    if len(engagement.subdomains) > 500:
        extra = f"<li class='muted'>... and {len(engagement.subdomains) - 500} more</li>"
    return (
        f'<section><h2>Attack surface</h2>'
        f"<details open><summary>{len(engagement.subdomains)} subdomain(s) / target(s)</summary>"
        f'<ul class="cols">{items}{extra}</ul></details></section>'
    )


def _osint_section(engagement: Engagement) -> str:
    if not engagement.osint:
        return ""
    rows = "".join(
        f"<tr><td>{escape(f.category)}</td><td>{escape(f.value)}</td></tr>"
        for f in engagement.osint
    )
    return (
        '<section><h2>OSINT</h2><table class="data"><thead><tr>'
        "<th>Source</th><th>Summary</th></tr></thead><tbody>"
        + rows
        + "</tbody></table></section>"
    )


def render(engagement: Engagement) -> str:
    accent = branding.COLOR_ACCENT
    accent_dark = branding.COLOR_ACCENT_DARK
    rating = engagement.risk_rating
    rating_color = {
        "Critical": branding.SEVERITY_COLORS["critical"],
        "High": branding.SEVERITY_COLORS["high"],
        "Medium": branding.SEVERITY_COLORS["medium"],
        "Low": branding.SEVERITY_COLORS["low"],
        "Informational": branding.SEVERITY_COLORS["info"],
        "Clean": "#16a34a",
    }.get(rating, "#64748b")

    kpis = "".join(
        [
            _kpi(len(engagement.hosts), "Hosts"),
            _kpi(engagement.total_open_ports, "Open ports"),
            _kpi(len(engagement.vulnerabilities), "Findings"),
            _kpi(engagement.risk_score, "Risk score", accent=True),
        ]
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(branding.NAME)} Report — {escape(engagement.name)}</title>
<meta name="generator" content="{escape(branding.LONG_NAME)} v{branding.VERSION}">
<style>
:root {{
  --accent: {accent};
  --bg: #f6f8fb; --card: #ffffff; --ink: #0f172a; --muted: #64748b;
  --line: #e2e8f0; --rating: {rating_color};
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --accent: {accent_dark}; --bg: #0b1220; --card: #111a2e; --ink: #e8eef9;
    --muted: #94a3b8; --line: #22304a;
  }}
}}
* {{ box-sizing: border-box; }}
body {{
  margin: 0; background: var(--bg); color: var(--ink);
  font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}}
.wrap {{ max-width: 1040px; margin: 0 auto; padding: 32px 16px 64px; }}
header.report {{
  display: flex; flex-wrap: wrap; gap: 16px; align-items: center;
  justify-content: space-between; border-bottom: 3px solid var(--accent);
  padding-bottom: 20px; margin-bottom: 28px;
}}
.brand {{ font-size: 26px; font-weight: 800; letter-spacing: -0.5px; }}
.brand span {{ color: var(--accent); }}
.brand small {{ display:block; font-size:12px; font-weight:500; color:var(--muted); letter-spacing:0; }}
.rating {{
  text-align: right; font-size: 13px; color: var(--muted);
}}
.rating b {{
  display:inline-block; margin-top:4px; padding:4px 12px; border-radius:999px;
  background: var(--rating)1a; color: var(--rating); border:1px solid var(--rating)66;
  font-size: 15px;
}}
.kpis {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 30px; }}
.kpi {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 18px; }}
.kpi.accent {{ border-color: var(--accent); }}
.kpi-value {{ font-size: 30px; font-weight: 800; line-height: 1; }}
.kpi-label {{ color: var(--muted); font-size: 13px; margin-top: 6px; }}
section {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 22px; margin-bottom: 22px; }}
h2 {{ margin: 0 0 16px; font-size: 19px; }}
h3 {{ margin: 0 0 6px; font-size: 16px; }}
table.data {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
table.data th {{ text-align: left; color: var(--muted); font-weight: 600; border-bottom: 2px solid var(--line); padding: 8px 10px; }}
table.data td {{ border-bottom: 1px solid var(--line); padding: 8px 10px; vertical-align: top; }}
.badge {{ display:inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }}
.mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12.5px; }}
.src {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.4px; }}
.wrap-cell, td.wrap {{ word-break: break-word; max-width: 360px; }}
.muted {{ color: var(--muted); }}
.bar-row {{ display: grid; grid-template-columns: 90px 1fr 40px; align-items: center; gap: 10px; margin: 7px 0; }}
.bar-label {{ font-size: 13px; }}
.bar-track {{ background: var(--line); border-radius: 999px; height: 10px; overflow: hidden; }}
.bar-fill {{ height: 100%; border-radius: 999px; min-width: 2px; }}
.bar-count {{ text-align: right; font-variant-numeric: tabular-nums; font-size: 13px; }}
.host {{ padding: 14px 0; border-bottom: 1px dashed var(--line); }}
.host:last-child {{ border-bottom: 0; }}
.host-meta {{ color: var(--muted); font-size: 13px; margin-bottom: 10px; }}
ul.cols {{ columns: 3; list-style: none; padding: 0; margin: 10px 0 0; font-size: 13px; }}
ul.cols li {{ padding: 1px 0; break-inside: avoid; }}
summary {{ cursor: pointer; font-weight: 600; }}
footer {{ color: var(--muted); font-size: 12px; text-align: center; margin-top: 28px; }}
.legal {{ margin-top: 10px; font-size: 11px; }}
@media (max-width: 720px) {{ .kpis {{ grid-template-columns: repeat(2, 1fr); }} ul.cols {{ columns: 1; }} }}
@media print {{ body {{ background: #fff; }} section, .kpi {{ break-inside: avoid; }} }}
</style>
</head>
<body>
<div class="wrap">
  <header class="report">
    <div class="brand">{escape(branding.NAME)}<span>.</span>
      <small>{escape(branding.TAGLINE)}</small>
    </div>
    <div class="rating">
      Engagement: <b style="background:none;border:0;color:var(--ink);padding:0">{escape(engagement.name)}</b><br>
      Generated: {escape(engagement.generated_at)}<br>
      Risk rating: <b>{escape(rating)} ({engagement.risk_score})</b>
    </div>
  </header>

  <div class="kpis">{kpis}</div>

  <section>
    <h2>Executive summary</h2>
    <p>The assessment identified <b>{len(engagement.hosts)}</b> live host(s),
    <b>{engagement.total_open_ports}</b> open port(s) and
    <b>{len(engagement.vulnerabilities)}</b> finding(s). The overall risk
    rating is <b>{escape(rating)}</b>.</p>
    {_severity_bars(engagement)}
  </section>

  <section>
    <h2>Findings</h2>
    {_findings_table(engagement)}
  </section>

  <section>
    <h2>Hosts &amp; services</h2>
    {_hosts_section(engagement)}
  </section>

  {_subdomains_section(engagement)}
  {_osint_section(engagement)}

  <footer>
    {escape(branding.LONG_NAME)} v{branding.VERSION} &middot; {escape(branding.ENGINE_CREDIT)}
    <div class="legal">For authorised security testing only. Ensure you have
    explicit written permission to test every in-scope target.</div>
  </footer>
</div>
</body>
</html>
"""
