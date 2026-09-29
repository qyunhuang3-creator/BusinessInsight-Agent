"""Profiling → 紧凑 schema；与业务问题无关，保留所有表的结构优先于样本。"""

from copy import deepcopy
import json
from src.tools.sql_tool import TABLE_FILES

# 数据集语义元数据，不是 GMV 任务白名单，也不宣称复合键已由 profiler 验证。
GRAINS = {
    "orders": ("order", ["order_id"]),
    "order_items": ("order item", ["order_id", "order_item_id"]),
    "customers": ("order-associated customer record, not unique person", ["customer_id"]),
    "products": ("product", ["product_id"]),
    "sellers": ("seller", ["seller_id"]),
    "payments": ("payment record, multiple per order", ["order_id", "payment_sequential"]),
    "reviews": ("review record; uniqueness not assumed", []),
    "geolocation": ("location record; zip prefix not unique", []),
    "category_translation": ("category translation", ["product_category_name"]),
}


def schema_summary(profile, budget=6000):
    """无损保留原对象。预算不足按信息类别逐步缩减，不截取 JSON 字符串。

    all columns 默认可见；只传非零缺失计数。关系仅根据同名字段和单列
    主键候选推断，未验证外键。可用于任意 profiler 表；Olist 附加已知语义。
    """
    aliases = {filename.removesuffix(".csv"): table for table, filename in TABLE_FILES.items()}
    tables = []
    for raw in sorted(profile.get("tables", []), key=lambda t: t["table_name"]):
        name = aliases.get(raw["table_name"], raw["table_name"])
        columns = list(raw.get("columns", []))
        candidates = list(raw.get("primary_key_candidates", []))
        grain, keys = GRAINS.get(name, ("not established; validate candidate keys", candidates))
        table = {"table_name": name, "row_count": raw.get("row_count"), "columns": columns,
                 "candidate_keys": candidates, "grain": grain,
                 "grain_key": [k for k in keys if k in columns]}
        missing = {k: v for k, v in raw.get("missing_values", {}).items() if v}
        if missing:
            table["nonzero_missing"] = missing
        tables.append(table)
    relationships = []
    for table in tables:
        for column in table["columns"]:
            if not column.endswith("_id"):
                continue
            targets = [t for t in tables if t is not table and column in t["candidate_keys"]
                       and t["grain_key"] == [column]]
            for target in targets:
                relationships.append(f"{table['table_name']}.{column} -> {target['table_name']}.{column}")
    result = {"status": profile.get("status"), "kind": "compact_schema", "tables": tables,
              "relationships": relationships,
              "notes": "候选键来自profiling；grain为数据集语义，复合键需SQL验证；关系为潜在关联，未验证外键。样本/dtypes/零缺失/重复统计有意省略。",
              "truncated": bool(profile.get("truncated", False))}
    if profile.get("errors"):
        result["errors"] = [{"code": e.get("code"), "table_name": e.get("table_name")} for e in profile["errors"]]

    def size():
        return len(json.dumps(result, ensure_ascii=False))

    if size() <= budget:
        return result
    result.update(truncated=True, context_truncated=True, budget_omissions=[])
    for field in ("nonzero_missing",):
        for table in tables:
            table.pop(field, None)
    result["budget_omissions"].append("nonzero_missing")
    if size() > budget:
        result.pop("relationships", None)
        result["budget_omissions"].append("relationships")
    # 轮流收缩最宽表的非键字段；关键表不会因输入顺序靠后而优先丢失。
    while size() > budget:
        eligible = [t for t in tables if any(c not in t["grain_key"] and c not in t["candidate_keys"] for c in t["columns"])]
        if not eligible:
            break
        table = max(eligible, key=lambda t: len(json.dumps(t["columns"])))
        for column in reversed(table["columns"]):
            if column not in table["grain_key"] and column not in table["candidate_keys"]:
                table["columns"].remove(column)
                table["columns_omitted"] = table.get("columns_omitted", 0) + 1
                break
    if size() > budget:
        result["budget_omissions"].append("table_details")
        result["tables"] = [{"table_name": t["table_name"], "grain_key": t["grain_key"]} for t in tables]
    while size() > budget and result["tables"]:
        result["tables"].pop()
        result["tables_omitted"] = result.get("tables_omitted", 0) + 1
    if size() > budget:
        return {"status": profile.get("status"), "kind": "compact_schema", "tables": [],
                "truncated": True, "tables_omitted": len(tables)}
    return deepcopy(result)
