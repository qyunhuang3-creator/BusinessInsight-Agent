import unittest
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
from unittest.mock import patch
from src.tools import sql_tool
from src.context import AgentContext
from src.planner import Planner, MockPlanner
from src.agent import BusinessInsightAgent


class SequencePlanner(Planner):
    def __init__(self, actions):
        self.actions = iter(actions)

    def next_action(self, context):
        return next(self.actions)


def action(name, **arguments):
    return {"action": name, "arguments": arguments, "reason": "test"}


class AgentTests(unittest.TestCase):
    def test_loop_with_real_sql_tool(self):
        with tempfile.TemporaryDirectory(dir=sql_tool.PROJECT_ROOT / "tests") as folder:
            database = Path(folder) / "test.db"
            with closing(sqlite3.connect(database)) as connection, connection:
                connection.execute("CREATE TABLE orders (order_id TEXT)")
                connection.executemany("INSERT INTO orders VALUES (?)", [("a",), ("b",)])
            with patch.object(sql_tool, "DB_PATH", database):
                result = BusinessInsightAgent(MockPlanner()).run(MockPlanner.DEMO_QUERY)
            self.assertEqual(result["status"], "finished")
            self.assertEqual(result["answer"], "数据里一共有 2 个订单。")

    def test_context_history_and_bounded_copy(self):
        context = AgentContext("question")
        context.iteration = 1
        action_id = context.add_action(action("run_sql", query="SELECT 1"))
        observation = {"status": "ok", "rows": [[i] for i in range(1000)], "row_count": 1000}
        context.add_observation(observation, action_id)
        observation["rows"][0][0] = -1
        saved = context.latest_observation()
        self.assertEqual(saved["data"]["rows"][0], [0])
        self.assertEqual(len(saved["data"]["rows"]), 5)
        self.assertEqual(saved["data"]["rows_context_omitted"], 995)
        context.add_finding("verified", action_id)
        self.assertEqual(context.findings[0]["evidence_action_id"], action_id)
        with self.assertRaises(ValueError):
            context.add_finding("unverified", 99)

    def test_mock_uses_tool_result_not_hardcoded_count(self):
        calls = []
        def tool(query):
            calls.append(query)
            return {"status": "ok", "columns": ["order_count"], "rows": [[42]], "row_count": 1}
        agent = BusinessInsightAgent(MockPlanner(), {"run_sql": tool})
        result = agent.run(MockPlanner.DEMO_QUERY)
        self.assertEqual(result["status"], "finished")
        self.assertIn("42", result["answer"])
        self.assertEqual(len(calls), 1)
        self.assertEqual([e["type"] for e in result["context"]["history"]], ["action", "observation", "action"])
        self.assertEqual(result["context"]["iteration"], 2)
        self.assertIn("42", agent.run(MockPlanner.DEMO_QUERY)["answer"])

    def test_registry_supports_inspection(self):
        planner = SequencePlanner([action("inspect_data"), action("finish")])
        agent = BusinessInsightAgent(planner, {"inspect_data": lambda: {"status": "ok", "tables": []}})
        self.assertEqual(agent.run("inspect")["status"], "finished")
        self.assertEqual(set(BusinessInsightAgent(MockPlanner()).tool_registry), {"inspect_data", "run_sql"})

    def test_unknown_tool(self):
        result = BusinessInsightAgent(SequencePlanner([action("missing"), action("finish")])).run("test")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["context"]["history"][1]["data"]["error"]["code"], "unknown_tool")

    def test_invalid_arguments_and_tool_failures(self):
        def exploding():
            raise RuntimeError("failed")
        cases = [(action("tool", unexpected=1), lambda: {"status": "ok"}, "invalid_arguments"),
                 (action("tool"), exploding, "tool_exception"),
                 (action("tool"), lambda: [], "invalid_observation"),
                 (action("tool"), lambda: {"status": "error", "error": {"code": "sql_error"}}, "sql_error")]
        for call, tool, code in cases:
            with self.subTest(code=code):
                result = BusinessInsightAgent(SequencePlanner([call, action("finish")]), {"tool": tool}).run("test")
                self.assertEqual(result["status"], "error")
                self.assertEqual(result["context"]["history"][1]["data"]["error"]["code"], code)

    def test_invalid_planner_action(self):
        for invalid in [None, {}, action("finish", extra=1), {"action": "run_sql", "arguments": [], "reason": "x"}]:
            result = BusinessInsightAgent(SequencePlanner([invalid])).run("test")
            self.assertEqual(result["status"], "error")
            self.assertEqual(result["context"]["history"][0]["data"]["error"]["code"], "invalid_action")

    def test_planner_exception(self):
        result = BusinessInsightAgent(SequencePlanner([])).run("test")
        self.assertEqual(result["status"], "error")

    def test_iteration_limit(self):
        planner = SequencePlanner([action("tool")] * 20)
        calls = []
        def tool():
            calls.append(1)
            return {"status": "ok"}
        result = BusinessInsightAgent(planner, {"tool": tool}, max_iterations=3).run("test")
        self.assertEqual(result["status"], "max_iterations")
        self.assertEqual(result["context"]["iteration"], 3)
        self.assertEqual(len(calls), 3)

    def test_failed_sql_does_not_create_finding(self):
        agent = BusinessInsightAgent(MockPlanner(), {"run_sql": lambda query: {"status": "error"}})
        result = agent.run(MockPlanner.DEMO_QUERY)
        self.assertEqual(result["context"]["findings"], [])
        self.assertEqual(result["status"], "error")


if __name__ == "__main__":
    unittest.main()
