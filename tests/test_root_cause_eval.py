from copy import deepcopy
import json
from pathlib import Path
import re
import unittest
from unittest.mock import Mock, patch

from evals.root_cause_eval import evaluate, expectations, flatten
from src.context import AgentContext
from src.llm.llm_planner import LLMPlanner
from src.llm.skill_loader import analysis_skill, SKILL_PATH

ROOT = Path(__file__).resolve().parents[1]


def fixture():
    # 人造评测fixture，不是实际Agent成功运行，不调用数据库或网络。
    truth = {"previous_month": "2000-01", "current_month": "2000-02", "gmv_change": -100.0, "gmv_mom_pct": -20.0,
             "volume_effect": -80., "aov_effect": -20., "order_mom_pct": -15., "aov_mom_pct": -5.,
             "comparable_months": ["2000-01", "2000-02"], "drill_parent": "region", "drill_member": "R",
             "top_dimensions": {"category": {"member": "C", "absolute_change": -50., "contribution_to_total_decline_pct": 50.}},
             "drill_top": {"category": {"member": "C", "absolute_change": -25.}}}
    assessment, history = {}, []
    aid = 0
    for name, expected in expectations(truth).items():
        aid += 1
        values = flatten(expected)
        history.extend([{"type": "action", "action_id": aid, "data": {"action": "run_sql", "arguments": {"query": "SELECT 1"}}},
                        {"type": "observation", "action_id": aid, "data": {"status": "ok", "columns": list(values), "rows": [list(values.values())]}}])
        assessment[name] = {"actual": deepcopy(expected), "evidence": [{"claim": key, "action_id": aid, "column": key, "row": 0} for key in values]}
    history.append({"type": "action", "action_id": aid+1, "data": {"action": "finish"}})
    assessment.update(statements=[{"text": "可能存在流量影响", "kind": "hypothesis", "validation_needed": "需流量数据"}],
                      hypothesis_review={"scope": "external_human", "reviewer": "test reviewer", "complete": True},
                      grain_review={"scope": "external_human", "reviewer": "test reviewer", "reason": "synthetic fixture", "passed": True, "action_ids": list(range(1,aid+1))})
    return {"status": "finished", "answer": "synthetic answer", "context": {"history": history}}, truth, assessment


class RootCauseEvalTests(unittest.TestCase):
    def test_pass_fail_partial(self):
        run, truth, review = fixture()
        self.assertEqual(evaluate(run, truth, review)["counts"], {"PASS": 10, "FAIL": 0, "PARTIAL": 0})
        review["anomaly_detection"]["actual"]["gmv_change"] = 123
        self.assertEqual(evaluate(run, truth, review)["dimensions"]["anomaly_detection"]["status"], "FAIL")
        del review["anomaly_detection"]
        self.assertEqual(evaluate(run, truth, review)["dimensions"]["anomaly_detection"]["status"], "PARTIAL")

    def test_float_tolerance(self):
        run, truth, review = fixture()
        review["decomposition_correctness"]["actual"]["volume_effect"] += 0.005
        self.assertEqual(evaluate(run, truth, review)["dimensions"]["decomposition_correctness"]["status"], "PASS")

    def test_missing_or_invalid_evidence_not_pass(self):
        for mode in ("missing", "wrong_row", "failed_tool"):
            run, truth, review = fixture()
            if mode == "missing":
                review["anomaly_detection"]["evidence"] = []
            elif mode == "wrong_row":
                for ref in review["anomaly_detection"]["evidence"]:
                    ref["row"] = 99
            else:
                for e in run["context"]["history"]:
                    if e["type"] == "observation":
                        e["data"]["status"] = "error"
            self.assertNotEqual(evaluate(run, truth, review)["dimensions"]["anomaly_detection"]["status"], "PASS")

    def test_hypothesis_as_fact_fails(self):
        run, truth, review = fixture()
        review["statements"] = [{"text": "流量减少导致下降", "kind": "evidence", "causal": True, "supported": False}]
        self.assertEqual(evaluate(run, truth, review)["dimensions"]["hypothesis_discipline"]["status"], "FAIL")

    def test_unsafe_sql_and_no_finish(self):
        run, truth, review = fixture()
        run["context"]["history"][0]["data"]["arguments"]["query"] = "DELETE FROM orders"
        run["status"] = "error"
        result = evaluate(run, truth, review)
        self.assertEqual(result["dimensions"]["tool_safety"]["status"], "FAIL")
        self.assertEqual(result["dimensions"]["task_completion"]["status"], "FAIL")

    def test_skill_has_no_ground_truth_answers(self):
        skill = SKILL_PATH.read_text(encoding="utf-8")
        truth = json.loads((ROOT/"output/reports/gmv_ground_truth_summary.json").read_text(encoding="utf-8"))
        forbidden = [truth["current_month"], "26.36", *[row["member"] for row in truth["top_dimensions"].values()]]
        for value in forbidden:
            self.assertNotIn(value, skill)
        self.assertTrue(skill.startswith("---\nname: root-cause-analysis\n"))
        self.assertIn("description:", skill)

    def test_planner_isolation_and_routing(self):
        self.assertEqual(analysis_skill("数据里一共有多少订单？"), "")
        client = Mock(return_value={"status": "error", "error": {"code": "mock"}})
        original = Path.read_text
        reads = []
        def guarded(path, *args, **kwargs):
            reads.append(path.resolve())
            self.assertEqual(path.resolve(), SKILL_PATH.resolve())
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", guarded):
            LLMPlanner(client).next_action(AgentContext("为什么销售额下降？"))
        self.assertEqual(reads, [SKILL_PATH.resolve()])
        prompt = client.call_args.args[0][0]["content"]
        self.assertIn("# 业务异动归因", prompt)
        self.assertNotIn("2017-12", prompt)
        for source in (ROOT/"src").rglob("*.py"):
            self.assertIsNone(re.search(r"(?:from|import)\s+evals\b", source.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
