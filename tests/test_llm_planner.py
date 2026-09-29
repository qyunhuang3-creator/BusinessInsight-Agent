import json
import unittest
from unittest.mock import Mock
from src.context import AgentContext
from src.agent import BusinessInsightAgent
from src.llm.llm_planner import LLMPlanner


class LLMPlannerTests(unittest.TestCase):
    def test_diagnostics_reach_agent_history(self):
        response = {"status": "error", "error": {"code": "http_error"}, "http_status": 429,
                    "error_type": "http_error", "openrouter_code": "429", "provider_error": "Rate limited",
                    "model": "openrouter/free", "timeout": False, "json_parse_error": False, "api_calls": 1}
        result = BusinessInsightAgent(LLMPlanner(Mock(return_value=response))).run("test")
        details = result["context"]["history"][0]["data"]["diagnostics"]
        self.assertEqual(details["http_status"], 429)
        self.assertEqual(details["provider_error"], "Rate limited")

    def get(self, value):
        return LLMPlanner(Mock(return_value={"status": "ok", "result": value})).next_action(AgentContext("test"))

    def test_allowed_actions(self):
        for name, args in [("run_sql", {"query": "SELECT COUNT(*) FROM orders"}),
                           ("inspect_data", {}), ("finish", {"answer": "有2个订单"})]:
            value = {"action": name, "arguments": args, "reason": "证据"}
            self.assertEqual(self.get(value), value)

    def test_invalid_json(self):
        self.assertEqual(self.get("not json")["error"]["code"], "content_json_error")

    def test_invalid_actions(self):
        for value in [{}, {"action": "bad", "arguments": {}, "reason": "x"},
                      {"action": "run_sql", "arguments": {}, "reason": "x"},
                      {"action": "finish", "arguments": {}, "reason": "x"},
                      {"action": "inspect_data", "arguments": [], "reason": "x"},
                      {"action": "run_sql", "arguments": {"query": "DELETE FROM orders"}, "reason": "x"}]:
            self.assertEqual(self.get(value)["status"], "error")

    def test_api_error_and_agent_stop(self):
        planner = LLMPlanner(Mock(return_value={"status": "error", "error": {"code": "http_error"}, "api_calls": 1}))
        tool = Mock()
        result = BusinessInsightAgent(planner, {"run_sql": tool}).run("test")
        self.assertEqual(result["status"], "error")
        self.assertEqual(planner.api_calls, 1)
        tool.assert_not_called()

    def test_context_bound(self):
        context = AgentContext("q" * 5000)
        for _ in range(100):
            context.add_observation({"status": "ok", "rows": [["x" * 10000]] * 1000})
        text = LLMPlanner()._context(context)
        self.assertLess(len(text), 24000)
        self.assertGreater(json.loads(text)["history_omitted"], 0)

    def test_full_loop_finish_answer(self):
        client = Mock(side_effect=[
            {"status": "ok", "api_calls": 1, "result": {"action": "run_sql", "arguments": {"query": "SELECT COUNT(*) FROM orders"}, "reason": "需要证据"}},
            {"status": "ok", "api_calls": 1, "result": {"action": "finish", "arguments": {"answer": "2个订单"}, "reason": "已有证据"}}])
        planner = LLMPlanner(client)
        result = BusinessInsightAgent(planner, {"run_sql": lambda query: {"status": "ok", "rows": [[2]]}}).run("test")
        self.assertEqual(result["answer"], "2个订单")
        self.assertEqual(result["context"]["iteration"], 2)
        self.assertEqual(planner.api_calls, 2)
        self.assertIn('"rows": [[2]]', client.call_args.args[0][1]["content"])


if __name__ == "__main__":
    unittest.main()
