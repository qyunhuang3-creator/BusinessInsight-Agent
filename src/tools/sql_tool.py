"""SQLite 数据层与只读查询 Tool；仅使用 Python 标准库。"""

import argparse
import csv
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import time

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "data" / "olist.db"
TABLE_FILES = {
    "orders": "olist_orders_dataset.csv",
    "order_items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "products": "olist_products_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "sellers": "olist_sellers_dataset.csv",
    "geolocation": "olist_geolocation_dataset.csv",
    "category_translation": "product_category_name_translation.csv",
}
INTEGER_COLUMNS = {
    "order_item_id", "payment_sequential", "payment_installments", "review_score",
    "product_name_lenght", "product_description_lenght", "product_photos_qty",
    "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm",
}
REAL_COLUMNS = {"price", "freight_value", "payment_value", "geolocation_lat", "geolocation_lng"}
MAX_ROWS = 1000
QUERY_TIMEOUT_SECONDS = 5


def _project_path(path):
    path = Path(path)
    path = (PROJECT_ROOT / path).resolve() if not path.is_absolute() else path.resolve()
    if not path.is_relative_to(PROJECT_ROOT):
        raise ValueError("路径必须位于项目目录内")
    return path


def _quote(name):
    return '"' + name.replace('"', '""') + '"'


def build_database():
    """一次性导入九张 CSV。存在数据库时拒绝覆盖；失败不发布半成品。

    保留重复记录与原始行粒度。空字段转 NULL；ID、邮编、时间为 TEXT，
    数量为 INTEGER，金额和经纬度为 REAL。每批最多 5000 行。
    """
    destination = _project_path(DB_PATH)
    if destination.exists():
        raise FileExistsError(f"数据库已存在，不覆盖：{destination}")
    sources = {table: _project_path(PROJECT_ROOT / "data" / filename)
               for table, filename in TABLE_FILES.items()}
    for path in sources.values():
        if not path.is_file():
            raise FileNotFoundError(f"CSV 不存在：{path}")
    counts = {}
    with tempfile.TemporaryDirectory(prefix="sqlite_import_", dir=destination.parent) as folder:
        temporary_db = Path(folder) / "olist.db"
        connection = sqlite3.connect(temporary_db)
        try:
            connection.execute("PRAGMA temp_store=MEMORY")
            with connection:
                for table, path in sources.items():
                    with path.open(encoding="utf-8-sig", newline="") as source:
                        reader = csv.reader(source, strict=True)
                        columns = next(reader)
                        if not columns or any(not c for c in columns) or len(set(columns)) != len(columns):
                            raise ValueError(f"{table}: 无效字段名")
                        types = ["INTEGER" if c in INTEGER_COLUMNS else "REAL" if c in REAL_COLUMNS else "TEXT"
                                 for c in columns]
                        schema = ", ".join(f"{_quote(c)} {t}" for c, t in zip(columns, types))
                        connection.execute(f"CREATE TABLE {_quote(table)} ({schema})")
                        insert = f"INSERT INTO {_quote(table)} VALUES ({','.join('?' for _ in columns)})"
                        batch = []
                        counts[table] = 0
                        for row in reader:
                            if len(row) != len(columns):
                                raise ValueError(f"{table}: CSV 第 {reader.line_num} 行字段数不一致")
                            values = [None if v == "" else int(v) if t == "INTEGER" else float(v) if t == "REAL" else v
                                      for v, t in zip(row, types)]
                            batch.append(values)
                            counts[table] += 1
                            if len(batch) == 5000:
                                connection.executemany(insert, batch)
                                batch.clear()
                        if batch:
                            connection.executemany(insert, batch)
                    for column in columns:
                        if column.endswith("_id"):
                            connection.execute(
                                f"CREATE INDEX {_quote('idx_' + table + '_' + column)} "
                                f"ON {_quote(table)} ({_quote(column)})"
                            )
        finally:
            connection.close()
        if destination.exists():
            raise FileExistsError(f"数据库已存在，不覆盖：{destination}")
        temporary_db.rename(destination)
    return {"status": "ok", "database": str(destination), "tables": counts}


def run_sql(query):
    """执行一条 SELECT / WITH ... SELECT，返回可序列化的 dict。

    rows 为按 columns 顺序排列的二维列表，NULL 转为 None。
    row_count 是实际返回行数，最多 MAX_ROWS；truncated 表示尚有更多行。
    空结果仍为 ok。错误返回 error.code/message，不抛出常规 SQL 异常。
    """
    def error(code, message):
        return {"status": "error", "columns": [], "rows": [], "row_count": 0,
                "truncated": False, "error": {"code": code, "message": message}}

    if not isinstance(query, str) or not query.strip():
        return error("invalid_query", "请输入非空 SQL 字符串")
    # 这里只检查入口语句；实际操作由 SQLite authorizer 判定，避免关键词误判。
    without_comments = re.sub(r"\A(?:\s|--[^\n]*(?:\n|$)|/\*[\s\S]*?\*/)*", "", query)
    if not re.match(r"(?:SELECT|WITH)\b", without_comments, flags=re.IGNORECASE):
        return error("read_only_violation", "仅允许 SELECT 或 WITH ... SELECT")
    try:
        database = _project_path(DB_PATH)
        if not database.is_file():
            return error("database_not_found", "数据库不存在，请先运行 build_database()")
    except (OSError, ValueError) as exc:
        return error("database_error", str(exc))

    denied = False

    def authorize(action, arg1, arg2, database_name, trigger):
        nonlocal denied
        allowed = action in {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ,
                             sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() == "load_extension":
            allowed = False
        if not allowed:
            denied = True
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY

    connection = None
    try:
        connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
        connection.execute("PRAGMA query_only=ON")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.set_authorizer(authorize)
        deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        cursor = connection.execute(query)
        rows = cursor.fetchmany(MAX_ROWS + 1)
        # bytes（如 SELECT x'AB'）转换为带类型的 hex 对象，保证 JSON 可序列化。
        return {"status": "ok", "columns": [c[0] for c in cursor.description],
                "rows": [[{"type": "blob", "hex": v.hex()} if isinstance(v, bytes) else v for v in row]
                         for row in rows[:MAX_ROWS]],
                "row_count": min(len(rows), MAX_ROWS), "truncated": len(rows) > MAX_ROWS}
    except sqlite3.Error as exc:
        message = str(exc)
        code = ("read_only_violation" if denied else "table_not_found" if "no such table" in message
                else "query_timeout" if "interrupted" in message else "sql_error")
        return error(code, message)
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="导入 Olist CSV 或执行只读 SQL")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--import-data", action="store_true")
    group.add_argument("--query")
    args = parser.parse_args()
    try:
        result = build_database() if args.import_data else run_sql(args.query)
    except (OSError, ValueError, csv.Error, sqlite3.Error, StopIteration) as exc:
        result = {"status": "error", "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "ok" else 1)
