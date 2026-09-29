from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from src.context import AgentContext
from src.schema_summary import schema_summary
from src.tools.data_profiler import inspect_data, PROJECT_ROOT
from src.llm.llm_planner import LLMPlanner


class SchemaSummaryTests(unittest.TestCase):
    def profile(self):
        specs = [
            ("olist_orders_dataset", ["order_id", "customer_id", "order_purchase_timestamp"], ["order_id"]),
            ("olist_order_items_dataset", ["order_id", "order_item_id", "product_id", "seller_id", "price"], []),
            ("olist_products_dataset", ["product_id", "product_category_name"], ["product_id"]),
            ("olist_customers_dataset", ["customer_id", "customer_state"], ["customer_id"]),
            ("olist_sellers_dataset", ["seller_id", "seller_state"], ["seller_id"]),
        ]
        return {"status": "ok", "tables": [{"table_name": name, "row_count": 10,
                "columns": cols, "primary_key_candidates": keys, "sample": [{"text": "x" * 10000}],
                "dtypes": {c: "object" for c in cols}, "missing_values": {c: 0 for c in cols}}
                for name, cols, keys in specs]}

    def test_context_summary_and_raw_unchanged(self):
        profile = self.profile()
        original = deepcopy(profile)
        context = AgentContext("any task")
        context.add_observation(profile)
        compact = context.latest_observation()["data"]
        self.assertEqual(profile, original)
        self.assertEqual(compact["kind"], "compact_schema")
        self.assertNotIn("sample", json.dumps(compact))
        self.assertLessEqual(len(json.dumps(compact, ensure_ascii=False)), 6000)
        for table in compact["tables"]:
            self.assertIn("grain", table)
            self.assertIn("candidate_keys", table)
        items = next(t for t in compact["tables"] if t["table_name"] == "order_items")
        self.assertEqual(items["grain_key"], ["order_id", "order_item_id"])
        self.assertIn("order_items.order_id -> orders.order_id", compact["relationships"])

    def test_order_independent_and_visible_to_planner(self):
        profile = self.profile()
        first = schema_summary(profile)
        profile["tables"].reverse()
        self.assertEqual(first, schema_summary(profile))
        context = AgentContext("GMV")
        context.add_observation(profile)
        sent = json.loads(LLMPlanner()._context(context))["schema"]
        self.assertEqual({t["table_name"] for t in sent["tables"]}, {"orders", "order_items", "products", "customers", "sellers"})

    def test_over_budget_structured_and_flagged(self):
        profile = self.profile()
        for t in profile["tables"]:
            t["columns"].extend([f"long_column_{i}" for i in range(200)])
        result = schema_summary(profile, budget=2500)
        self.assertTrue(result["truncated"])
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), 2500)
        self.assertEqual(len(result["tables"]), 5)
        self.assertNotIn("preview", result)

    def test_profiler_still_full_and_generic_tables(self):
        with tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "tests") as folder:
            (Path(folder) / "inventory.csv").write_text("item_id,stock\na,1\nb,\n", encoding="utf-8")
            full = inspect_data(folder)
            table = full["tables"][0]
            for field in ("sample", "dtypes", "missing_values", "duplicate_rows"):
                self.assertIn(field, table)
            compact = schema_summary(full)["tables"][0]
            self.assertEqual(compact["table_name"], "inventory")
            self.assertEqual(compact["nonzero_missing"], {"stock": 1})
            self.assertIn("item_id", compact["candidate_keys"])


if __name__ == "__main__":
    unittest.main()
