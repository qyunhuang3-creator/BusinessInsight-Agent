"""使用项目内临时 CSV 测试，不读写真实业务数据。"""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.tools.data_profiler import PROJECT_ROOT, inspect_data, print_inspection


class InspectDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=PROJECT_ROOT / "tests")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def write_csv(self, name, text):
        path = self.directory / name
        path.write_text(text, encoding="utf-8", newline="")
        return path

    def test_statistics_sample_and_read_only(self):
        path = self.write_csv("orders.CSV", "order_id,value,note\n001,10,a\n002,,b\n002,,b\n003,20,c\n")
        original = path.read_bytes()
        result = inspect_data(self.directory)
        table = result["tables"][0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(table["table_name"], "orders")
        self.assertEqual(table["row_count"], 4)
        self.assertEqual(table["column_count"], 3)
        self.assertEqual(table["columns"], ["order_id", "value", "note"])
        self.assertEqual(table["dtypes"]["order_id"], "string")
        self.assertEqual(table["missing_values"], {"order_id": 0, "value": 2, "note": 0})
        self.assertEqual(table["duplicate_rows"], 1)
        self.assertEqual(len(table["sample"]), 3)
        self.assertEqual(table["sample"][0]["order_id"], "001")
        self.assertIsNone(table["sample"][1]["value"])
        self.assertEqual(table["primary_key_candidates"], [])
        self.assertEqual(table["potential_relation_fields"], ["order_id"])
        json.dumps(result, allow_nan=False)
        self.assertEqual(path.read_bytes(), original)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            print_inspection(result)
        self.assertIn("orders", output.getvalue())

    def test_primary_key_and_multiline_sample(self):
        self.write_csv("customers.csv", 'customer_id,note\n001,"hello\nworld"\n002,repeat\n003,repeat\n')
        table = inspect_data(self.directory)["tables"][0]
        self.assertEqual(table["row_count"], 3)
        self.assertEqual(table["primary_key_candidates"], ["customer_id"])
        self.assertEqual(table["sample"][0]["note"], "hello\nworld")

    def test_missing_directory(self):
        result = inspect_data(self.directory / "missing")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["errors"][0]["code"], "directory_not_found")

    def test_no_csv(self):
        self.write_csv("notes.txt", "not a csv")
        self.assertEqual(inspect_data(self.directory)["errors"][0]["code"], "no_csv_files")

    def test_bad_csv_does_not_stop_other_tables(self):
        self.write_csv("bad.csv", 'id,value\n1,"unclosed')
        self.write_csv("good.csv", "id,value\n1,2\n")
        result = inspect_data(self.directory)
        self.assertEqual(result["status"], "partial")
        self.assertEqual([t["table_name"] for t in result["tables"]], ["good"])
        self.assertEqual(result["errors"][0]["code"], "csv_read_failed")

    def test_empty_file_and_invalid_encoding(self):
        self.write_csv("empty.csv", "")
        (self.directory / "invalid.csv").write_bytes(b"id\n\xff\n")
        result = inspect_data(self.directory)
        self.assertEqual(result["status"], "error")
        self.assertEqual(len(result["errors"]), 2)

    def test_header_only(self):
        self.write_csv("empty.csv", "id,value\n")
        table = inspect_data(self.directory)["tables"][0]
        self.assertEqual(table["row_count"], 0)
        self.assertEqual(table["sample"], [])
        self.assertEqual(table["primary_key_candidates"], [])

    def test_default_directory_ignores_working_directory(self):
        (self.directory / "data").mkdir()
        (self.directory / "data" / "one.csv").write_text("id\n1\n", encoding="utf-8")
        with patch("src.tools.data_profiler.PROJECT_ROOT", self.directory):
            result = inspect_data()
        self.assertEqual(result["data_dir"], str(self.directory / "data"))
        self.assertEqual(result["status"], "ok")

    def test_permission_error(self):
        self.write_csv("locked.csv", "id\n1\n")
        with patch("src.tools.data_profiler.pd.read_csv", side_effect=PermissionError("denied")):
            result = inspect_data(self.directory)
        self.assertEqual(result["errors"][0]["code"], "csv_read_failed")

    def test_file_instead_of_directory(self):
        path = self.write_csv("one.csv", "id\n1\n")
        self.assertEqual(inspect_data(path)["errors"][0]["code"], "not_a_directory")


if __name__ == "__main__":
    unittest.main()
