import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import run_business_insight_demo as demo


class BusinessDemoTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=demo.ROOT / "tests")
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name)

    def run_demo(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as stdout:
            code = demo.run_demo(output_dir=self.output, **kwargs)
        trace = json.loads((self.output / "demo_trace.json").read_text(encoding="utf-8"))
        return code, trace, stdout.getvalue()

    def test_offline_no_key_no_network_and_numbers(self):
        with patch.dict(os.environ, {}, clear=True), patch("urllib.request.OpenerDirector.open", side_effect=AssertionError("network forbidden")), patch.object(demo, "live_run", side_effect=AssertionError("live forbidden")):
            code, trace, text = self.run_demo()
        self.assertEqual(code, 0)
        self.assertFalse(trace["fallback_used"])
        self.assertEqual(trace["api_calls"], 0)
        self.assertEqual(len(trace["stages"]), 7)
        bundle = demo.example_bundle()
        self.assertIn(demo.headline(bundle), text)
        values = next(e["values"] for e in bundle["evidence"] if e["id"] == "gmv")
        self.assertIn(f"{values['current_gmv']:,.2f}", text)
        self.assertEqual(trace["completion_status"], "completed_replay")

    def test_protected_deliverables_unchanged(self):
        files = list((demo.ROOT / "output/tableau").glob("*.csv")) + list((demo.ROOT / "output/tableau").glob("*.twb"))
        files += list((demo.ROOT / "output/reports").glob("*ground_truth*"))
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        self.run_demo()
        self.assertTrue(files)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in files})

    def test_provider_errors_fallback_without_secret_or_retry(self):
        for error in ("http_error", "timeout", "content_json_error", "action_validation_error"):
            run = {"status": "error", "context": {"iteration": 1, "history": [{"type": "observation", "data": {"status": "error", "error": {"code": error, "message": "Authorization secret-value"}, "diagnostics": {"http_status": 429}}}]}}
            with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-private-key"}), patch.object(demo, "live_run", return_value=(run, 1)) as runner:
                code, trace, text = self.run_demo(mode="agent")
            self.assertEqual(code, 0)
            runner.assert_called_once()
            self.assertTrue(trace["fallback_used"])
            self.assertEqual(trace["agent_status"], "error")
            self.assertEqual(trace["completion_status"], "completed_replay")
            serialized = json.dumps(trace)
            for secret in ("test-private-key", "secret-value", "Authorization"):
                self.assertNotIn(secret, serialized)
            self.assertIn("NOT an Agent-generated conclusion", text)

    def test_runner_exception_graceful(self):
        with patch.object(demo, "live_run", side_effect=RuntimeError("secret-value")):
            code, trace, text = self.run_demo(mode="agent")
        self.assertEqual(code, 0)
        self.assertIsNone(trace["api_calls"])
        self.assertNotIn("secret-value", text)

    def test_unsupported_offline_question(self):
        with patch.object(demo, "example_bundle", side_effect=AssertionError("must not replay")):
            code, trace, text = self.run_demo(question="What is next year's profit?")
        self.assertEqual(code, 2)
        self.assertEqual(trace["completion_status"], "unsupported_question")
        self.assertIsNone(trace["report_path"])
        self.assertIn("不是实时通用 Agent", text)

    def test_agent_unrelated_question_does_not_get_gmv_fallback(self):
        code, trace, _ = self.run_demo(mode="agent", question="Profit next year?", agent_runner=lambda q: ({"status": "error"}, 1))
        self.assertEqual(code, 2)
        self.assertEqual(trace["completion_status"], "agent_failed_no_matching_replay")
        self.assertFalse(trace["fallback_used"])

    def test_agent_success_does_not_read_ground_truth(self):
        run = {"status": "finished", "context": {"iteration": 2, "history": [
            {"type": "action", "action_id": 1, "data": {"action": "run_sql", "arguments": {"query": "SELECT 42 AS count"}}},
            {"type": "observation", "action_id": 1, "data": {"status": "ok", "columns": ["count"], "rows": [[42]], "row_count": 1}}]}}
        with patch.object(demo, "example_bundle", side_effect=AssertionError("truth leak")):
            code, trace, _ = self.run_demo(mode="agent", agent_runner=lambda q: (run, 2))
        self.assertEqual(code, 0)
        self.assertFalse(trace["fallback_used"])
        self.assertEqual(trace["completion_status"], "agent_finished_report_partial")
        report = (demo.ROOT / trace["report_path"]).read_text(encoding="utf-8")
        self.assertIn("42", report)
        self.assertNotIn("2017-12", report)

    def test_missing_evidence_graceful(self):
        with patch.object(demo, "example_bundle", side_effect=FileNotFoundError("private path")):
            code, trace, text = self.run_demo()
        self.assertEqual(code, 1)
        self.assertEqual(trace["completion_status"], "failed")
        self.assertNotIn("Traceback", text)

    def test_direct_script_cli_no_traceback(self):
        # Unsupported input exercises the direct-script bootstrap without touching reports.
        result = subprocess.run([sys.executable, str(demo.ROOT / "scripts/run_business_insight_demo.py"), "--question", "unsupported"],
            cwd=self.output, capture_output=True, text=True, encoding="utf-8", timeout=15)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_safe_question_and_summary(self):
        self.assertEqual(demo.safe("Authorization: Bearer anything"), "[Sensitive text omitted]")
        self.assertEqual(demo.safe("sk-test-1234"), "[REDACTED]")
        _, trace, _ = self.run_demo(question="Why did Product GMV decline?")
        self.assertTrue((self.output / "demo_summary.md").is_file())
        self.assertEqual(trace["question"], "Why did Product GMV decline?")
