"""Tests for email-auth (SPF/DMARC) and TLS exposure checks."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from jarvis.asm.email_security import analyze_dmarc, analyze_spf, check_domain
from jarvis.asm.tls import cert_expiry_exposure, protocol_exposure


class SpfTest(unittest.TestCase):
    def test_missing_spf(self):
        exp = analyze_spf([])
        self.assertIsNotNone(exp)
        self.assertEqual(exp.severity, "medium")

    def test_permissive_spf(self):
        exp = analyze_spf(["v=spf1 +all"])
        self.assertEqual(exp.severity, "high")

    def test_strict_spf_is_clean(self):
        self.assertIsNone(analyze_spf(["v=spf1 include:_spf.example.com -all"]))


class DmarcTest(unittest.TestCase):
    def test_missing_dmarc(self):
        self.assertIsNotNone(analyze_dmarc([]))

    def test_policy_none_is_weak(self):
        exp = analyze_dmarc(["v=DMARC1; p=none; rua=mailto:x@e.com"])
        self.assertEqual(exp.severity, "low")

    def test_policy_reject_is_clean(self):
        self.assertIsNone(analyze_dmarc(["v=DMARC1; p=reject"]))


class TlsTest(unittest.TestCase):
    def test_expired_cert(self):
        past = datetime.now(timezone.utc) - timedelta(days=5)
        exp = cert_expiry_exposure("host:443", past)
        self.assertEqual(exp.severity, "high")
        self.assertIn("Expired", exp.title)

    def test_near_expiry(self):
        soon = datetime.now(timezone.utc) + timedelta(days=10)
        exp = cert_expiry_exposure("host:443", soon)
        self.assertEqual(exp.severity, "low")

    def test_healthy_cert_is_clean(self):
        far = datetime.now(timezone.utc) + timedelta(days=200)
        self.assertIsNone(cert_expiry_exposure("host:443", far))

    def test_weak_protocol(self):
        self.assertIsNotNone(protocol_exposure("host", "TLSv1.0"))
        self.assertIsNone(protocol_exposure("host", "TLSv1.3"))


class LootSourcingTest(unittest.TestCase):
    def test_check_domain_offline_from_loot(self):
        with tempfile.TemporaryDirectory() as tmp:
            osint = Path(tmp) / "osint"
            osint.mkdir()
            (osint / "dns.txt").write_text(
                'example.com TXT "v=spf1 +all"\n'
                '_dmarc.example.com TXT "v=DMARC1; p=none"\n',
                encoding="utf-8",
            )
            exposures = check_domain("example.com", Path(tmp), live=False)
            sevs = sorted(e.severity for e in exposures)
            # +all SPF (high) + p=none DMARC (low)
            self.assertEqual(sevs, ["high", "low"])
            self.assertTrue(all(e.asset == "example.com" for e in exposures))


if __name__ == "__main__":
    unittest.main()
