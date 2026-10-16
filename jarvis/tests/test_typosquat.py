"""Tests for brand-protection typosquat candidate generation."""

from __future__ import annotations

import unittest

from jarvis.asm.build import build_attack_surface
from jarvis.asm.model import Asset, AssetKind, AttackSurface
from jarvis.asm.typosquat import enrich_typosquat, generate_candidates


class GenerateTest(unittest.TestCase):
    def test_basic_properties(self):
        cands = generate_candidates("example.com", max_candidates=60)
        self.assertTrue(cands)
        self.assertLessEqual(len(cands), 60)
        self.assertNotIn("example.com", cands)  # original excluded
        self.assertEqual(len(cands), len(set(cands)))  # deduped

    def test_includes_known_techniques(self):
        cands = set(generate_candidates("example.com", max_candidates=200))
        self.assertIn("exmple.com", cands)       # omission
        self.assertIn("example.net", cands)      # TLD swap
        self.assertIn("exampl3.com", cands)      # homoglyph e->3
        self.assertIn("secure-example.com", cands)  # affix

    def test_apex_reduction_from_subdomain(self):
        cands = generate_candidates("www.example.com")
        self.assertTrue(all(c.endswith((".com", ".net", ".org", ".co", ".io",
                                        ".info", ".biz", ".online", ".site", ".xyz"))
                            for c in cands))
        self.assertNotIn("www.example.com", cands)

    def test_deterministic(self):
        self.assertEqual(
            generate_candidates("acme.io"), generate_candidates("acme.io")
        )


class EnrichTest(unittest.TestCase):
    def test_watchlist_recorded_offline(self):
        surface = AttackSurface(name="t")
        surface.assets.append(
            Asset(kind=AssetKind.DOMAIN.value, value="example.com")
        )
        added = enrich_typosquat(surface, live=False)
        self.assertEqual(added, 0)  # no live check => no exposures
        self.assertIn("typosquat", surface.extras)
        self.assertIn("example.com", surface.extras["typosquat"]["watchlist"])
        self.assertFalse(surface.extras["typosquat"]["checked_live"])


if __name__ == "__main__":
    unittest.main()
