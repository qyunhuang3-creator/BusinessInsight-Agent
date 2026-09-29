from copy import deepcopy
import unittest
from src.context import AgentContext
from src.llm.context_history import planner_context


class HistoryTests(unittest.TestCase):
    def context(self):
        c = AgentContext("GMV")
        for iteration in range(1, 5):
            c.iteration = iteration
            query = "SELECT order_id FROM orders o" if iteration == 3 else "SELECT o.order_id FROM orders o"
            aid = c.add_action({"action": "run_sql", "arguments": {"query": query}, "reason": "old-reason" if iteration < 4 else "fixed alias"})
            obs = {"status": "ok", "columns": ["month", "gmv"], "rows": [[str(i), i] for i in range(24)], "truncated": False}
            if iteration == 1:
                obs = {"status": "ok", "kind": "compact_schema", "tables": [{"table_name": "orders", "columns": ["order_id"]}]}
                # schema is already compact; save directly for this view test
                c.history.append({"type": "observation", "iteration": iteration, "action_id": aid, "data": obs})
                continue
            if iteration == 3:
                obs = {"status": "error", "error": {"code": "sql_error", "message": "ambiguous order_id"}}
            c.add_observation(obs, aid)
        c.iteration = 5
        return c

    def test_recent_details_and_old_summary(self):
        c = self.context()
        original = deepcopy(c.history)
        view = planner_context(c)
        self.assertEqual(c.history, original)
        self.assertEqual(len(view["history"]), 2)
        self.assertEqual(view["history"][0]["data"]["reason"], "fixed alias")
        self.assertNotIn("old-reason", str(view))
        self.assertEqual(len(view["history"][1]["data"]["rows"]), 24)

    def test_resolved_error_and_schema_single_copy(self):
        view = planner_context(self.context())
        error = next(e for e in view["history_summary"] if e["action_id"] == 3)
        self.assertEqual(error["resolved_by_action"], 4)
        self.assertNotIn("arguments", error)
        self.assertEqual(str(view).count("compact_schema"), 1)

    def test_older_evidence_retained(self):
        view = planner_context(self.context())
        self.assertEqual(len(view["evidence"][0]["data"]["rows"]), 24)
        self.assertEqual(view["evidence"][0]["action_id"], 2)


if __name__ == "__main__":
    unittest.main()
