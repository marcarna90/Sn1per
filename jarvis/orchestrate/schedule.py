"""Generate cron schedules to re-run a campaign periodically.

Pure helpers here (testable); the actual crontab install lives in the CLI and
shells out to ``crontab``. Scheduled runs use ``--resume`` so a re-run only
picks up what changed / what has not completed yet.
"""

from __future__ import annotations

from pathlib import Path

# Cadence -> cron expression (02:00 local). 'weekly' = Sundays, 'monthly' = 1st.
CADENCES = {
    "daily": "0 2 * * *",
    "weekly": "0 2 * * 0",
    "monthly": "0 2 1 * *",
}


def cron_expression(cadence: str | None, custom: str | None = None) -> str:
    if custom:
        return custom.strip()
    if cadence in CADENCES:
        return CADENCES[cadence]
    raise ValueError(
        f"Unknown cadence '{cadence}'. Use one of {', '.join(CADENCES)} or --cron."
    )


def build_cron_line(
    campaign_path: str,
    repo_dir: str,
    loot_base: str,
    cadence: str | None = None,
    custom_cron: str | None = None,
    sniper_bin: str = "sniper",
) -> str:
    """Return a full crontab line that re-runs the campaign on schedule."""
    expr = cron_expression(cadence, custom_cron)
    repo = Path(repo_dir).resolve()
    campaign = Path(campaign_path).resolve()
    cmd = (
        f"cd {repo} && ./jarvis-cli run {campaign} "
        f"--loot-base {loot_base} --sniper-bin {sniper_bin} --resume -q "
        f">> {repo}/jarvis-cron.log 2>&1"
    )
    return f"{expr} {cmd}"
