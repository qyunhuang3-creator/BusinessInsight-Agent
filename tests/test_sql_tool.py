from contextlib import closing
import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from src.tools import sql_tool


class SqlToolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=sql_tool.PROJECT_ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "data").mkdir()
        self.db = self.root / "data" / "olist.db"
        self.root_patch = patch.object(sql_tool, "PROJECT_ROOT", self.root)
        self.db_patch = patch.object(sql_tool, "DB_PATH", self.db)
        self.root_patch.start()
        self.db_patch.start()
        self.addCleanup(self.root_patch.stop)
        self.addCleanup(self.db_patch.stop)
        with closing(sqlite3.connect(self.db)) as connection, connection:
            connection.execute("CREATE TABLE orders (order_id TEXT, amount REAL)")
            connection.executemany("INSERT INTO orders VALUES (?, ?)", [("001", 10), ("002", None)])

    def test_select_and_cte(self):
        for query in ["SELECT COUNT(*) AS total FROM orders", "/* note */ WITH x AS (SELECT * FROM orders) SELECT COUNT(*) AS total FROM x"]:
            result = sql_tool.run_sql(query)
            self.assertEqual(result["status"], "ok")
            self.assertEqual(result["columns"], ["total"])
            self.assertEqual(result["rows"], [[2]])
            self.assertEqual(result["row_count"], 1)

    def test_empty_and_null(self):
        result = sql_tool.run_sql("SELECT order_id FROM orders WHERE 0")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["rows"], [])
        self.assertEqual(result["columns"], ["order_id"])
        self.assertEqual(sql_tool.run_sql("SELECT amount FROM orders WHERE order_id='002'")["rows"], [[None]])

    def test_errors(self):
        for query, code in [("SELECT FROM orders", "sql_error"), ("SELECT * FROM absent", "table_not_found"), ("", "invalid_query"), (None, "invalid_query")]:
            self.assertEqual(sql_tool.run_sql(query)["error"]["code"], code)
        self.db.unlink()
        self.assertEqual(sql_tool.run_sql("SELECT 1")["error"]["code"], "database_not_found")
        self.assertFalse(self.db.exists())

    def test_reject_writes_and_multiple_statements(self):
        before = self.db.read_bytes()
        queries = ["INSERT INTO orders VALUES ('003', 2)", "UPDATE orders SET amount=0",
                   "DELETE FROM orders", "DROP TABLE orders", "ALTER TABLE orders ADD x TEXT",
                   "CREATE TABLE x (id)", "WITH x AS (SELECT 1) DELETE FROM orders",
                   "SELECT 1; DROP TABLE orders", "PRAGMA user_version=1", "ATTACH ':memory:' AS other",
                   "SELECT load_extension('missing')"]
        for query in queries:
            with self.subTest(query=query):
                self.assertEqual(sql_tool.run_sql(query)["status"], "error")
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(sql_tool.run_sql("SELECT 'DROP TABLE orders' AS text")["status"], "ok")

    def test_limit_and_timeout(self):
        with patch.object(sql_tool, "MAX_ROWS", 1):
            result = sql_tool.run_sql("SELECT * FROM orders")
        self.assertEqual(result["row_count"], 1)
        self.assertTrue(result["truncated"])
        with patch.object(sql_tool, "QUERY_TIMEOUT_SECONDS", -1):
            result = sql_tool.run_sql("WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM n WHERE x<100000) SELECT SUM(x) FROM n")
        self.assertEqual(result["error"]["code"], "query_timeout")

    def test_import_preserves_values_and_refuses_overwrite(self):
        self.db.unlink()
        sources = []
        for filename in sql_tool.TABLE_FILES.values():
            path = self.root / "data" / filename
            path.write_text('order_id,price,review_score,note\n001,2.5,4,"line1\nline2"\n002,,,\n', encoding="utf-8", newline="")
            sources.append(path)
        before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources]
        result = sql_tool.build_database()
        self.assertEqual(result["tables"], {t: 2 for t in sql_tool.TABLE_FILES})
        self.assertEqual(sql_tool.run_sql("SELECT * FROM orders ORDER BY order_id")["rows"], [["001", 2.5, 4, "line1\nline2"], ["002", None, None, None]])
        self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in sources])
        with self.assertRaises(FileExistsError):
            sql_tool.build_database()

    def test_failed_import_does_not_publish_database(self):
        self.db.unlink()
        for filename in sql_tool.TABLE_FILES.values():
            (self.root / "data" / filename).write_text("order_id,price\n001,invalid-number\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            sql_tool.build_database()
        self.assertFalse(self.db.exists())


if __name__ == "__main__":
    unittest.main()
