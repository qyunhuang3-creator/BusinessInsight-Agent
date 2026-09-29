import json
import unittest
from src.context import AgentContext, OBSERVATION_CHAR_BUDGET
from src.llm.llm_planner import LLMPlanner, SYSTEM_PROMPT


class GMVContextTests(unittest.TestCase):
    def test_complete_monthly_trend(self):
        context = AgentContext("GMV")
        rows = [[f"month-{i}", i * 100, i] for i in range(25)]
        context.add_observation({"status": "ok", "columns": ["month", "gmv", "orders"],
                                 "rows": rows, "row_count": 25, "truncated": False})
        saved = context.latest_observation()["data"]
        self.assertEqual(saved["rows"], rows)
        self.assertFalse(saved["truncated"])
        sent = json.loads(LLMPlanner()._context(context))
        self.assertEqual(sent["history"][0]["data"]["rows"], rows)

    def test_large_rows_budget_and_flag(self):
        context = AgentContext("GMV")
        context.add_observation({"status": "ok", "columns": ["text"],
                                 "rows": [["x" * 10000] for _ in range(40)], "row_count": 40})
        saved = context.latest_observation()["data"]
        self.assertTrue(saved["truncated"])
        self.assertTrue(saved["context_truncated"])
        self.assertLessEqual(len(json.dumps(saved, ensure_ascii=False)), OBSERVATION_CHAR_BUDGET)
        self.assertEqual(saved["row_count"], 40)

    def test_tool_truncation_preserved(self):
        context = AgentContext("GMV")
        context.add_observation({"status": "ok", "columns": ["gmv"], "rows": [[1]], "truncated": True})
        self.assertTrue(context.latest_observation()["data"]["truncated"])

    def test_business_constraints(self):
        for rule in ("SUM(order_items.price)", "COUNT(DISTINCT order_id)", "AOV", "Grain", "Evidence",
                     "Hypothesis", "上一个自然月", "不完整", "Contribution", "customer state", "seller", "truncated=true"):
            self.assertIn(rule, SYSTEM_PROMPT)


if __name__ == "__main__":
    unittest.main()
