"""只读 CSV 数据检查工具：返回可 JSON 序列化的 Observation。

运行方式：python -m src.tools.data_profiler [项目内的数据目录]
"""

import argparse
import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def inspect_data(data_dir: str | Path | None = None) -> dict:
    """扫描目录直属 CSV（扩展名不区分大小写），逐表返回检查结果。

    默认目录为项目根目录下的 data，相对路径也以项目根目录为基准。
    仅允许项目内路径。CSV 按 UTF-8/BOM 读取，使用 pandas 默认缺失值
    规则；id 和邮编字段保留字符串，避免丢失前导零。其他类型由 pandas
    推断，不自动解析日期。每次在内存中处理一张完整表，仅输出前三行。

    status 为 ok / partial / error；单表失败不阻止其他表检查。
    primary_key_candidates 仅为非空且唯一的单列候选，不验证业务语义，
    不推断复合主键。potential_relation_fields 仅按 *_id 命名识别。
    duplicate_rows 是全字段相同、排除首次出现后的重复行数量。
    """
    directory = Path(data_dir) if data_dir is not None else Path("data")
    if not directory.is_absolute():
        directory = PROJECT_ROOT / directory
    directory = directory.resolve()
    result = {"status": "ok", "data_dir": str(directory), "tables": [], "errors": []}

    def fail(code: str, message: str) -> dict:
        result["status"] = "error"
        result["errors"].append({"code": code, "message": message})
        return result

    if not directory.is_relative_to(PROJECT_ROOT):
        return fail("outside_project", "数据目录必须位于当前项目内。")
    if not directory.exists():
        return fail("directory_not_found", "数据目录不存在。")
    if not directory.is_dir():
        return fail("not_a_directory", "指定路径不是目录。")
    try:
        csv_files = sorted(
            (p for p in directory.iterdir() if p.suffix.lower() == ".csv"),
            key=lambda p: p.name,
        )
    except OSError as exc:
        return fail("directory_read_failed", str(exc))
    if not csv_files:
        return fail("no_csv_files", "数据目录中没有 CSV 文件。")

    for path in csv_files:
        try:
            if not path.resolve().is_relative_to(PROJECT_ROOT):
                raise ValueError("CSV 指向项目外部，已拒绝读取。")
            header = pd.read_csv(path, encoding="utf-8-sig", nrows=0)
            text_columns = {
                column: "string"
                for column in header.columns
                if column.lower() == "id"
                or column.lower().endswith("_id")
                or "zip_code" in column.lower()
            }
            frame = pd.read_csv(
                path, encoding="utf-8-sig", dtype=text_columns, low_memory=False,
                on_bad_lines="error",
            )
            missing = frame.isna().sum()
            result["tables"].append({
                "table_name": path.stem,
                "row_count": int(len(frame)),
                "column_count": int(len(frame.columns)),
                "columns": frame.columns.tolist(),
                "dtypes": {column: str(dtype) for column, dtype in frame.dtypes.items()},
                "missing_values": {column: int(count) for column, count in missing.items()},
                "duplicate_rows": int(frame.duplicated().sum()),
                "sample": json.loads(frame.head(3).to_json(orient="records", force_ascii=False)),
                "primary_key_candidates": [
                    column for column in frame.columns
                    if len(frame) > 0 and missing[column] == 0 and frame[column].is_unique
                ],
                "potential_relation_fields": [
                    column for column in frame.columns if column.lower().endswith("_id")
                ],
            })
            del frame
        except (OSError, UnicodeError, ValueError, pd.errors.ParserError) as exc:
            result["errors"].append({
                "table_name": path.stem,
                "code": "csv_read_failed",
                "message": str(exc),
            })
    if result["errors"]:
        result["status"] = "partial" if result["tables"] else "error"
    return result


def print_inspection(result: dict) -> None:
    """将 inspect_data 的返回值展示到终端；不重新读取 CSV。"""
    print(f"状态: {result['status']} | 目录: {result['data_dir']}")
    for table in result["tables"]:
        print(f"\n{table['table_name']}: {table['row_count']:,} 行 × {table['column_count']} 列")
        for column in table["columns"]:
            print(f"  {column}: {table['dtypes'][column]}, 缺失 {table['missing_values'][column]}")
        print(f"  重复行: {table['duplicate_rows']}")
        print(f"  单列主键候选: {', '.join(table['primary_key_candidates']) or '无'}")
        print(f"  潜在关联字段: {', '.join(table['potential_relation_fields']) or '无'}")
        print("  前 3 行样本:")
        print(json.dumps(table["sample"][:3], ensure_ascii=False, indent=2))
    for error in result["errors"]:
        print(f"错误 [{error['code']}] {error.get('table_name', '')}: {error['message']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="检查项目内的 CSV 数据")
    parser.add_argument("data_dir", nargs="?", default=None)
    args = parser.parse_args()
    observation = inspect_data(args.data_dir)
    print_inspection(observation)
    raise SystemExit(0 if observation["status"] == "ok" else 1)
