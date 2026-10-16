"""Tests for the Jarvis reporting engine.

Pure stdlib (unittest) so they run anywhere Sn1per runs, with no test
dependencies. Run from the repo root with:

    python3 -m unittest discover -s jarvis/tests
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from jarvis.report.collector import collect
from jarvis.report.generate import generate_reports
from jarvis.report.severity import normalize

FIXTURE = Path(__file__).parent / "fixtures" / "demo-workspace"


class SeverityTest(unittest.TestCase):
    def test_normalize_aliases(self):
        self.assertEqual(normalize("CRITICAL"), "critical")
        self.assertEqual(normalize("High"), "high")
        self.assertEqual(normalize("informational"), "info")
        self.assertEqual(normalize("moderate"), "medium")

    def test_normalize_unknown_defaults_to_info(self):
        self.assertEqual(normalize("banana"), "info")
        self.assertEqual(normalize(""), "info")


class CollectorTest(unittest.TestCase):
    def setUp(self):
        self.eng = collect(FIXTURE, name="Demo Lab Engagement")

    def test_hosts_and_ports(self):
        self.assertEqual(len(self.eng.hosts), 2)
        self.assertEqual(self.eng.total_open_ports, 7)
        web01 = next(h for h in self.eng.hosts if h.ip == "10.10.10.5")
        self.assertEqual(web01.target, "web01.demo.lab")
        self.assertIn("Ubuntu", web01.os)
        self.assertTrue(any(p.number == 3306 for p in web01.open_ports))

    def test_vulnerabilities_and_scoring(self):
        counts = self.eng.severity_counts()
        self.assertEqual(counts["critical"], 1)
        self.assertEqual(counts["high"], 2)
        # 1*5 + 2*4 + 2*3 + 1*2 + 2*1 = 23 (matches Sn1per's sc0pe formula)
        self.assertEqual(self.eng.risk_score, 23)
        self.assertEqual(self.eng.risk_rating, "Critical")

    def test_evidence_entity_cleanup(self):
        crit = next(v for v in self.eng.vulnerabilities if v.severity == "critical")
        self.assertNotIn("&lh;", crit.evidence)
        self.assertIn("<", crit.evidence)

    def test_subdomains_and_osint(self):
        self.assertIn("web01.demo.lab", self.eng.subdomains)
        categories = {o.category for o in self.eng.osint}
        self.assertIn("emails", categories)

    def test_missing_directory_raises(self):
        with self.assertRaises(FileNotFoundError):
            collect("/nonexistent/path/xyz")


class GenerateTest(unittest.TestCase):
    def test_all_text_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = generate_reports(
                FIXTURE, tmp, formats=["html", "md", "json"], name="Demo"
            )
            for fmt in ("html", "md", "json"):
                self.assertIn(fmt, results)
                self.assertTrue(Path(results[fmt]).is_file())

            html = Path(results["html"]).read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", html)
            self.assertIn("Executive summary", html)

            data = json.loads(Path(results["json"]).read_text(encoding="utf-8"))
            self.assertEqual(data["engagement"]["risk_score"], 23)

    def test_invalid_format_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                generate_reports(FIXTURE, tmp, formats=["docx"])

    def test_empty_workspace_still_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty-ws"
            empty.mkdir()
            out = Path(tmp) / "out"
            results = generate_reports(empty, out, formats=["html", "json"])
            self.assertTrue(Path(results["html"]).is_file())
            data = json.loads(Path(results["json"]).read_text(encoding="utf-8"))
            self.assertEqual(data["engagement"]["total_hosts"], 0)
            self.assertEqual(data["engagement"]["risk_rating"], "Clean")


if __name__ == "__main__":
    unittest.main()
