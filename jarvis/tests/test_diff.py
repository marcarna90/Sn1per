"""Tests for ASM change tracking (snapshots + diff)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jarvis.asm.diff import (
    diff_surfaces,
    latest_snapshot,
    load_snapshot,
    save_snapshot,
)
from jarvis.asm.model import Asset, AssetKind, AttackSurface, Exposure


def _surface(assets, exposures, name="t"):
    s = AttackSurface(name=name)
    s.assets = assets
    s.exposures = exposures
    return s


class DiffTest(unittest.TestCase):
    def test_detects_added_and_removed(self):
        prev = _surface(
            [Asset(AssetKind.IP.value, "10.0.0.1")],
            [Exposure("open_database", "db", "critical", asset="10.0.0.1:3306")],
        ).to_dict()
        curr = _surface(
            [Asset(AssetKind.IP.value, "10.0.0.1"), Asset(AssetKind.IP.value, "10.0.0.2")],
            [Exposure("misconfiguration", "headers", "medium", asset="10.0.0.2")],
        ).to_dict()
        d = diff_surfaces(prev, curr)
        self.assertEqual(d["assets"]["added_count"], 1)
        self.assertEqual(d["assets"]["removed_count"], 0)
        self.assertEqual(d["assets"]["unchanged_count"], 1)
        self.assertEqual(d["exposures"]["added_count"], 1)   # headers
        self.assertEqual(d["exposures"]["removed_count"], 1)  # db resolved

    def test_posture_delta(self):
        prev = _surface([], [Exposure("open_database", "db", "critical")]).to_dict()
        curr = _surface([], []).to_dict()  # resolved everything
        d = diff_surfaces(prev, curr)
        # before 75 (100-25), after 100 => +25
        self.assertEqual(d["posture"]["score_delta"], 25.0)
        self.assertTrue(d["posture"]["grade_change"])

    def test_no_change(self):
        s = _surface([Asset(AssetKind.IP.value, "10.0.0.1")], []).to_dict()
        d = diff_surfaces(s, s)
        self.assertEqual(d["assets"]["added_count"], 0)
        self.assertEqual(d["assets"]["removed_count"], 0)
        self.assertEqual(d["exposures"]["added_count"], 0)


class SnapshotTest(unittest.TestCase):
    def test_save_and_latest_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = _surface([Asset(AssetKind.IP.value, "10.0.0.1")], [])
            p1 = save_snapshot(s, tmp)
            self.assertTrue(Path(p1).is_file())
            latest = latest_snapshot(tmp)
            self.assertEqual(latest, p1)
            loaded = load_snapshot(latest)
            self.assertEqual(loaded["total_assets"], 1)

    def test_latest_none_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(latest_snapshot(tmp))


if __name__ == "__main__":
    unittest.main()
