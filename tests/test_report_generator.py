from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import Mock

from src.context import AgentContext
from src.report_generator import generate_report, baseline_report, report_schema, validate_report, sources_from_context


def fixture():
    return {"question": "为什么服务使用量变化？", "analysis_status": "partial", "origin": "test observation",
        "sources": {"q": {"status": "ok", "tool": "run_sql", "reference": "action_id=1", "query": "SELECT usage FROM aggregated_metrics",
            "data": {"rows": [[123.25, -0.2]], "columns": ["usage", "change_rate"]}}},
        "evidence": [{"id": "usage", "section": "anomaly_overview", "metric": "Service Usage", "period": "period B", "dimension": "region West",
            "source_id": "q", "values": {"usage": 123.25, "change_rate": -0.2}, "references": {"usage": ["rows", 0, 0], "change_rate": ["rows", 0, 1]}}],
        "hypotheses": {"h": "用户活动可能减少，尚需访问日志验证。"}, "limitations": {"l": "分析未完成，只有部分证据。"},
        "recommended_next_checks": {"n": "检查访问日志。"}}


class ReportGeneratorTests(unittest.TestCase):
    def test_evidence_preserved_and_inputs_unchanged(self):
        b = fixture(); original = deepcopy(b)
        r = generate_report(b)
        self.assertEqual(r["evidence"], b["evidence"])
        self.assertEqual(b, original)
        self.assertIn("123.25", r["markdown"])
        self.assertIn("action\\_id=1", r["markdown"])
        self.assertEqual(r["client_calls"], 0)

    def test_hypothesis_is_not_evidence(self):
        b = fixture(); r = generate_report(b)
        evidence = r["markdown"].split("## Evidence")[1].split("## Hypotheses")[0]
        self.assertNotIn(b["hypotheses"]["h"], evidence)
        self.assertIn("不属于 Evidence", r["markdown"])

    def test_numeric_tampering_rejected_before_client(self):
        b = fixture(); b["evidence"][0]["values"]["usage"] = 99999
        client = Mock()
        self.assertEqual(generate_report(b, client)["error"]["code"], "invalid_evidence")
        client.assert_not_called()

    def test_llm_cannot_inject_numbers_or_facts(self):
        b = fixture(); draft = baseline_report(b)
        draft["executive_summary"] = ["GMV fell 99999 due to promotions"]
        r = generate_report(b, Mock(return_value={"status": "ok", "result": draft}))
        self.assertEqual(r["mode"], "deterministic_fallback")
        self.assertNotIn("99999", r["markdown"])

    def test_api_failures_fallback_once(self):
        for code in ("http_error", "timeout", "api_error", "connection_error", "content_json_error"):
            with self.subTest(code=code):
                client = Mock(return_value={"status": "error", "http_status": 429, "error": {"code": code}})
                r = generate_report(fixture(), client)
                self.assertEqual(r["status"], "ok")
                self.assertEqual(r["mode"], "deterministic_fallback")
                client.assert_called_once()
                self.assertIn("123.25", r["markdown"])

    def test_exception_fallback_does_not_log_secret(self):
        r = generate_report(fixture(), Mock(side_effect=RuntimeError("Authorization secret-value")))
        self.assertEqual(r["fallback_reason"], "client_unavailable")
        self.assertNotIn("secret-value", json.dumps(r))

    def test_empty_or_invalid_output_fallback(self):
        for value in (None, "", {}, [], "{}", {"answer": "invented"}):
            with self.subTest(value=value):
                r = generate_report(fixture(), Mock(return_value={"status": "ok", "result": value}))
                self.assertEqual(r["mode"], "deterministic_fallback")
                self.assertIn("Recommended Next Checks", r["markdown"])

    def test_valid_structured_output(self):
        b = fixture(); client = Mock(return_value={"status": "ok", "result": baseline_report(b)})
        r = generate_report(b, client)
        self.assertEqual(r["mode"], "llm_reference_order")
        self.assertEqual(client.call_args.kwargs["json_schema"], report_schema(b))
        validate_report(r["report"], r["schema"])

    def test_dropped_or_moved_evidence_fallback(self):
        b = fixture()
        for field in ("evidence", "anomaly_overview"):
            draft = baseline_report(b); draft[field] = []
            self.assertEqual(generate_report(b, Mock(return_value={"status": "ok", "result": draft}))["mode"], "deterministic_fallback")

    def test_generic_partial_input_no_case_assumptions(self):
        r = generate_report(fixture())
        for text in ("2017-12", "SP", "cama_mesa_banho"):
            self.assertNotIn(text, r["markdown"])
        self.assertIn("partial", r["markdown"])
        self.assertIn("未提供已验证证据", r["markdown"])

    def test_empty_evidence_does_not_fabricate_success(self):
        b = fixture(); b["sources"] = {}; b["evidence"] = []
        r = generate_report(b)
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["evidence"], [])
        self.assertIn("生成成功不等于分析任务已完成", r["markdown"])

    def test_failed_and_missing_source_rejected(self):
        for change in ("error", "missing", "nan", "duplicate"):
            b = fixture()
            if change == "error": b["sources"]["q"]["status"] = "error"
            if change == "missing": b["evidence"][0]["references"]["usage"] = ["rows", 99, 0]
            if change == "nan": b["evidence"][0]["values"]["usage"] = float("nan")
            if change == "duplicate": b["evidence"].append(deepcopy(b["evidence"][0]))
            self.assertEqual(generate_report(b)["status"], "error")

    def test_context_adapter_uses_actual_observation(self):
        c = AgentContext("usage")
        aid = c.add_action({"action": "run_sql", "arguments": {"query": "SELECT 7"}, "reason": "test"})
        c.add_observation({"status": "ok", "columns": ["usage"], "rows": [[7]]}, aid)
        sources = sources_from_context(c)
        self.assertEqual(sources["action_1"]["data"]["rows"], [[7]])
        b = fixture(); b["sources"] = sources
        b["evidence"][0].update(source_id="action_1", values={"usage": 7}, references={"usage": ["rows", 0, 0]})
        self.assertEqual(generate_report(b)["status"], "ok")

    def test_module_has_no_ground_truth_or_network_import(self):
        import ast
        path = Path(__file__).resolve().parents[1] / "src/report_generator.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        modules = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(m and ("llm" in m or "eval" in m or "tools" in m) for m in modules))
        self.assertNotIn("gmv_ground_truth_summary.json", path.read_text(encoding="utf-8"))
