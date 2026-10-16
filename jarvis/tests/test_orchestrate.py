"""Tests for the Jarvis orchestration layer (stdlib unittest, no live scans)."""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from jarvis.orchestrate.config import CampaignError, parse_campaign
from jarvis.orchestrate.executor import DryRunExecutor, Executor
from jarvis.orchestrate.model import Task, TaskResult
from jarvis.orchestrate.runner import plan, run_campaign

FIXTURE = Path(__file__).parent / "fixtures" / "demo-workspace"

SAMPLE = {
    "campaign": "Unit Test",
    "workspace": "unit-ws",
    "targets": ["a.example", "b.example"],
    "workflow": [
        {"mode": "discover"},
        {"mode": "normal", "options": {"osint": True, "recon": True}},
        {"mode": "webscan", "parallel": 2},
    ],
    "report": {"formats": ["html", "json"]},
}


class _FakeExecutor(Executor):
    """Non-dry executor that marks tasks done without running anything."""

    dry_run = False

    def execute(self, task: Task) -> TaskResult:
        return TaskResult(task=task, status="done", returncode=0, note="fake")


class ConfigTest(unittest.TestCase):
    def test_parse_valid(self):
        c = parse_campaign(SAMPLE)
        self.assertEqual(c.name, "Unit Test")
        self.assertEqual(c.workspace, "unit-ws")
        self.assertEqual(len(c.workflow), 3)
        self.assertEqual(c.workflow[2].parallel, 2)
        self.assertEqual(c.report.formats, ["html", "json"])

    def test_string_phase_shorthand(self):
        c = parse_campaign({**SAMPLE, "workflow": ["discover", "normal"]})
        self.assertEqual([p.mode for p in c.workflow], ["discover", "normal"])

    def test_workspace_defaults_to_slug(self):
        data = dict(SAMPLE)
        data.pop("workspace")
        self.assertEqual(parse_campaign(data).workspace, "unit-test")

    def test_missing_name_rejected(self):
        with self.assertRaises(CampaignError):
            parse_campaign({"targets": ["x"], "workflow": ["normal"]})

    def test_empty_workflow_rejected(self):
        with self.assertRaises(CampaignError):
            parse_campaign({"campaign": "x", "targets": ["x"], "workflow": []})


class PlanTest(unittest.TestCase):
    def test_expands_targets_times_phases(self):
        c = parse_campaign(SAMPLE)
        batches = plan(c)
        self.assertEqual(len(batches), 3)  # one batch per phase
        self.assertEqual(sum(len(b) for b in batches), 6)  # 3 phases x 2 targets

    def test_command_flag_mapping(self):
        c = parse_campaign(SAMPLE)
        batches = plan(c)
        normal_cmd = batches[1][0].command
        self.assertIn("-o", normal_cmd)  # osint
        self.assertIn("-re", normal_cmd)  # recon
        self.assertIn("--noreport", normal_cmd)  # Jarvis owns reporting
        self.assertIn("-w", normal_cmd)
        self.assertIn("unit-ws", normal_cmd)


class RunTest(unittest.TestCase):
    def test_dry_run_all_done(self):
        c = parse_campaign(SAMPLE)
        result = run_campaign(c, executor=DryRunExecutor(), generate_report=False)
        self.assertTrue(result.dry_run)
        self.assertEqual(len(result.tasks), 6)
        self.assertEqual(len(result.failed), 0)

    def test_report_generated_after_campaign(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "demo-lab"
            shutil.copytree(FIXTURE, ws)
            c = parse_campaign(
                {
                    "campaign": "Demo",
                    "workspace": "demo-lab",
                    "targets": ["web01.demo.lab"],
                    "workflow": ["normal"],
                    "report": {"formats": ["html", "json"]},
                }
            )
            result = run_campaign(
                c,
                executor=_FakeExecutor(),
                workspace_dir=str(ws),
                generate_report=True,
            )
            self.assertIn("html", result.reports)
            self.assertIn("json", result.reports)
            self.assertTrue(Path(result.reports["html"]).is_file())
            # Campaign state is checkpointed into the workspace.
            state = ws / "scans" / "jarvis-campaign-state.json"
            self.assertTrue(state.is_file())
            data = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(data["campaign"], "Demo")
            self.assertFalse(data["dry_run"])


if __name__ == "__main__":
    unittest.main()
