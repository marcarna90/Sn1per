"""Tests for third-party scanner importers (nuclei / Nessus / OpenVAS)."""

from __future__ import annotations

import unittest
from pathlib import Path

from jarvis.report.collector import collect
from jarvis.report.importers import from_nessus, from_nuclei, from_openvas

FIXTURE = Path(__file__).parent / "fixtures" / "multitool"


class NucleiTest(unittest.TestCase):
    def test_parses_jsonl(self):
        vulns = from_nuclei(FIXTURE)
        self.assertEqual(len(vulns), 3)
        crit = next(v for v in vulns if v.severity == "critical")
        self.assertIn("Log4", crit.name)
        self.assertEqual(crit.location, "https://10.20.0.4/api")
        self.assertTrue(all(v.source == "nuclei" for v in vulns))


class NessusTest(unittest.TestCase):
    def test_parses_nessus(self):
        vulns = from_nessus(FIXTURE)
        self.assertEqual(len(vulns), 3)
        crit = next(v for v in vulns if v.severity == "critical")
        self.assertIn("Heartbleed", crit.name)
        self.assertEqual(crit.location, "10.20.0.4:443")
        # severity 0 maps to info, 2 -> medium
        self.assertEqual({v.severity for v in vulns}, {"critical", "medium", "info"})


class OpenvasTest(unittest.TestCase):
    def test_parses_openvas(self):
        vulns = from_openvas(FIXTURE)
        self.assertEqual(len(vulns), 2)
        high = next(v for v in vulns if v.severity == "high")
        self.assertIn("SMB Signing", high.name)
        self.assertEqual(high.location, "10.20.0.9:445/tcp")


class CollectMergeTest(unittest.TestCase):
    def test_collect_merges_all_sources(self):
        eng = collect(FIXTURE, name="Multitool")
        # 3 nuclei + 3 nessus + 2 openvas = 8 findings, none duplicated
        self.assertEqual(len(eng.vulnerabilities), 8)
        sources = {v.source for v in eng.vulnerabilities}
        self.assertEqual(sources, {"nuclei", "nessus", "openvas"})
        self.assertEqual(eng.severity_counts()["critical"], 2)
        # subfinder output folds into the attack surface
        self.assertIn("api.corp.example", eng.subdomains)

    def test_openvas_does_not_eat_nmap_xml(self):
        # The demo-workspace fixture has nmap XML but no GVM report; ensure the
        # OpenVAS importer ignores nmap scans (no false findings).
        demo = Path(__file__).parent / "fixtures" / "demo-workspace"
        self.assertEqual(from_openvas(demo), [])


if __name__ == "__main__":
    unittest.main()
