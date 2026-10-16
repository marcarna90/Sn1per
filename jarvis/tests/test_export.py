"""Tests for exporting workspace reports off the VM/container."""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from jarvis.export import bundle, collect_report_files, copy_to, primary_ip


def _make_workspace(tmp: str) -> Path:
    ws = Path(tmp) / "acme"
    reports = ws / "reports"
    reports.mkdir(parents=True)
    (reports / "acme-report.html").write_text("<html></html>", encoding="utf-8")
    (reports / "acme-report.json").write_text("{}", encoding="utf-8")
    (reports / "acme-attack-surface.pdf").write_bytes(b"%PDF-1.4 fake")
    (reports / "notes.txt").write_text("ignored", encoding="utf-8")  # not a report glob
    return ws


class CollectTest(unittest.TestCase):
    def test_collects_only_report_globs(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            files = collect_report_files(ws / "reports")
            names = sorted(f.name for f in files)
            self.assertEqual(
                names,
                ["acme-attack-surface.pdf", "acme-report.html", "acme-report.json"],
            )
            self.assertNotIn("notes.txt", names)

    def test_missing_dir_returns_empty(self):
        self.assertEqual(collect_report_files(Path("/nope/xyz")), [])


class BundleTest(unittest.TestCase):
    def test_bundle_creates_zip_with_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            archive = bundle(ws)
            self.assertTrue(archive.endswith(".zip"))
            self.assertTrue(Path(archive).is_file())
            with zipfile.ZipFile(archive) as zf:
                names = sorted(zf.namelist())
            self.assertEqual(
                names,
                ["acme-attack-surface.pdf", "acme-report.html", "acme-report.json"],
            )

    def test_bundle_out_as_explicit_zip_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            target = Path(tmp) / "out" / "custom.zip"
            archive = bundle(ws, out=target)
            self.assertEqual(archive, str(target))
            self.assertTrue(target.is_file())

    def test_bundle_raises_without_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            (empty / "reports").mkdir(parents=True)
            with self.assertRaises(FileNotFoundError):
                bundle(empty)

    def test_copy_to(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = _make_workspace(tmp)
            archive = bundle(ws)
            dest = Path(tmp) / "share"
            copied = copy_to(archive, dest)
            self.assertTrue(Path(copied).is_file())
            self.assertEqual(Path(copied).name, Path(archive).name)


class IpTest(unittest.TestCase):
    def test_primary_ip_returns_string(self):
        ip = primary_ip()
        self.assertIsInstance(ip, str)
        self.assertTrue(ip)  # never empty (falls back to 127.0.0.1)


if __name__ == "__main__":
    unittest.main()
