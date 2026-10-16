"""Attack-surface change tracking (continuous-monitoring diffs).

A snapshot is the JSON form of an :class:`AttackSurface`. Comparing the
current surface to the most recent prior snapshot yields what is *new*,
*resolved* and *unchanged* — assets and exposures — plus how the posture
grade moved. ``diff_surfaces`` is pure (dict in, dict out) and tested; the
snapshot helpers are thin filesystem wrappers.
"""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jarvis.asm.model import AttackSurface

SNAPSHOT_DIRNAME = "asm-snapshots"


def _asset_id(a: dict[str, Any]) -> str:
    return f"{a.get('kind', '')}:{str(a.get('value', '')).lower()}"


def _exposure_id(e: dict[str, Any]) -> str:
    return (f"{e.get('category', '')}|{str(e.get('asset', '')).lower()}|"
            f"{str(e.get('title', '')).lower()}")


def diff_surfaces(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    """Diff two surface ``to_dict()`` payloads. Returns a change summary."""
    prev_assets = {_asset_id(a): a for a in prev.get("assets", [])}
    curr_assets = {_asset_id(a): a for a in curr.get("assets", [])}
    a_added = [curr_assets[k] for k in curr_assets.keys() - prev_assets.keys()]
    a_removed = [prev_assets[k] for k in prev_assets.keys() - curr_assets.keys()]

    prev_exp = {_exposure_id(e): e for e in prev.get("exposures", [])}
    curr_exp = {_exposure_id(e): e for e in curr.get("exposures", [])}
    e_added = [curr_exp[k] for k in curr_exp.keys() - prev_exp.keys()]
    e_removed = [prev_exp[k] for k in prev_exp.keys() - curr_exp.keys()]

    def slim(e: dict[str, Any]) -> dict[str, Any]:
        return {
            "severity": e.get("severity", ""),
            "category": e.get("category", ""),
            "title": e.get("title", ""),
            "asset": e.get("asset", ""),
        }

    def slim_asset(a: dict[str, Any]) -> dict[str, Any]:
        return {"kind": a.get("kind", ""), "value": a.get("value", "")}

    p_before = prev.get("posture", {}) or {}
    p_after = curr.get("posture", {}) or {}
    score_before = p_before.get("score", 0)
    score_after = p_after.get("score", 0)
    grade_before = p_before.get("grade", "")
    grade_after = p_after.get("grade", "")
    grade_change = (
        f"{grade_before} -> {grade_after}"
        if grade_before and grade_before != grade_after
        else ""
    )

    return {
        "previous_at": prev.get("generated_at", ""),
        "current_at": curr.get("generated_at", ""),
        "assets": {
            "added": [slim_asset(a) for a in a_added],
            "removed": [slim_asset(a) for a in a_removed],
            "added_count": len(a_added),
            "removed_count": len(a_removed),
            "unchanged_count": len(curr_assets.keys() & prev_assets.keys()),
        },
        "exposures": {
            "added": [slim(e) for e in e_added],
            "removed": [slim(e) for e in e_removed],
            "added_count": len(e_added),
            "removed_count": len(e_removed),
            "unchanged_count": len(curr_exp.keys() & prev_exp.keys()),
        },
        "posture": {
            "score_before": score_before,
            "score_after": score_after,
            "score_delta": round(score_after - score_before, 1),
            "grade_before": grade_before,
            "grade_after": grade_after,
            "grade_change": grade_change,
        },
    }


# --------------------------------------------------------------------------
# snapshot persistence
# --------------------------------------------------------------------------
def snapshot_dir(base: str | os.PathLike) -> Path:
    return Path(base) / SNAPSHOT_DIRNAME


def save_snapshot(surface: AttackSurface, base: str | os.PathLike) -> str:
    d = snapshot_dir(base)
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    path = d / f"asm-{stamp}.json"
    # Avoid clobbering if two run in the same second.
    i = 1
    while path.exists():
        path = d / f"asm-{stamp}-{i}.json"
        i += 1
    path.write_text(json.dumps(surface.to_dict(), indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return str(path)


def latest_snapshot(base: str | os.PathLike) -> str | None:
    d = snapshot_dir(base)
    files = sorted(glob.glob(str(d / "asm-*.json")))
    return files[-1] if files else None


def load_snapshot(path: str | os.PathLike) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
