"""Tests for the ASM (attack surface management) layer."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jarvis.asm.build import build_attack_surface
from jarvis.asm.generate import generate_asm_reports
from jarvis.asm.model import grade_from_exposures, score_to_grade, Exposure
from jarvis.report.collector import collect

FIXTURE = Path(__file__).parent / "fixtures" / "demo-workspace"


class GradingTest(unittest.TestCase):
    def test_score_to_grade_bands(self):
        self.assertEqual(score_to_grade(95)[0], "A")
        self.assertEqual(score_to_grade(72)[0], "C")
        self.assertEqual(score_to_grade(10)[0], "F")

    def test_grade_from_exposures(self):
        exposures = [Exposure("open_database", "db", "critical")]
        score, letter, _ = grade_from_exposures(exposures)
        self.assertEqual(score, 75.0)  # 100 - 25
        self.assertEqual(letter, "C")

    def test_clean_surface_is_A(self):
        score, letter, _ = grade_from_exposures([])
        self.assertEqual(score, 100.0)
        self.assertEqual(letter, "A")


class BuildTest(unittest.TestCase):
    def setUp(self):
        self.eng = collect(FIXTURE, name="Demo")
        self.surface = build_attack_surface(self.eng, client="ACME")

    def test_assets_classified(self):
        counts = self.surface.asset_counts()
        self.assertGreaterEqual(counts["ip"], 2)
        self.assertGreaterEqual(counts["service"], 7)
        self.assertGreaterEqual(counts["subdomain"], 1)

    def test_open_database_exposure_from_mysql_port(self):
        cats = {e.category for e in self.surface.exposures}
        self.assertIn("open_database", cats)  # mysql:3306 in fixture
        self.assertIn("remote_access_exposed", cats)  # ssh:22

    def test_findings_mapped_to_categories(self):
        # fixture has an SSRF (vulnerable_service) and missing headers (misconfig)
        cats = {e.category for e in self.surface.exposures}
        self.assertIn("vulnerable_service", cats)
        self.assertIn("misconfiguration", cats)

    def test_posture_present(self):
        p = self.surface.posture()
        self.assertIn(p["grade"], list("ABCDF"))
        self.assertTrue(p["per_category"])

    def test_every_exposure_has_remediation(self):
        self.assertTrue(all(e.remediation for e in self.surface.exposures))


class GenerateTest(unittest.TestCase):
    def test_generates_technical_and_executive(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = generate_asm_reports(
                FIXTURE, tmp, formats=["html", "md", "json"], client="ACME",
                snapshot=False,
            )
            for key in ("html", "html_exec", "md", "json"):
                self.assertIn(key, results)
                self.assertTrue(Path(results[key]).is_file())
            tech = Path(results["html"]).read_text(encoding="utf-8")
            self.assertIn("Attack Surface", tech)
            self.assertIn("ACME", tech)
            exec_html = Path(results["html_exec"]).read_text(encoding="utf-8")
            self.assertIn("Executive", exec_html)
            data = json.loads(Path(results["json"]).read_text(encoding="utf-8"))
            self.assertIn("posture", data["attack_surface"])

    def test_no_executive_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = generate_asm_reports(
                FIXTURE, tmp, formats=["html"], executive=False, snapshot=False
            )
            self.assertIn("html", results)
            self.assertNotIn("html_exec", results)


if __name__ == "__main__":
    unittest.main()
