"""离线、证据驱动评测。只比较显式评审标注，不用 LLM 猜测自由文本。

assessment 是人工从 Agent 回答提取的 actual 和证据引用，不是 Agent Prompt。
缺失标注返回 PARTIAL；正确数字但没有可验证证据不能 PASS。
"""
import argparse
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
NAMES = ["metric_correctness", "period_correctness", "anomaly_detection", "decomposition_correctness",
         "dimension_attribution", "drill_down_quality", "evidence_grounding", "hypothesis_discipline",
         "tool_safety", "task_completion"]


def close(actual, expected):
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return type(actual) in (int, float) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-5, abs_tol=0.02)
    return actual == expected


def flatten(value, prefix=""):
    if isinstance(value, dict):
        return {k: v for name, item in value.items() for k, v in flatten(item, f"{prefix}.{name}".strip(".")).items()}
    return {prefix: value}


def expectations(truth):
    return {
        "metric_correctness": {"gmv": "SUM(order_items.price)", "orders": "COUNT(DISTINCT order_id) with valid items",
            "aov": "gmv/orders", "time": "order_purchase_timestamp", "status_scope": "all_valid_item_orders"},
        "period_correctness": {"comparable_months": truth["comparable_months"]},
        "anomaly_detection": {k: truth[k] for k in ("previous_month", "current_month", "gmv_change", "gmv_mom_pct")},
        "decomposition_correctness": {**{k: truth[k] for k in ("volume_effect", "aov_effect", "order_mom_pct", "aov_mom_pct")},
            "main_driver": "order_volume" if abs(truth["volume_effect"]) > abs(truth["aov_effect"]) else "aov"},
        "dimension_attribution": {d: {k: row[k] for k in ("member", "absolute_change", "contribution_to_total_decline_pct")}
                                  for d, row in truth["top_dimensions"].items()},
        "drill_down_quality": {"parent_dimension": truth["drill_parent"], "parent_member": truth["drill_member"],
            "children": {d: {k: row[k] for k in ("member", "absolute_change")} for d, row in truth["drill_top"].items()}},
    }


def evaluate(run, truth, assessment=None):
    assessment = assessment or {}
    history = run.get("context", {}).get("history", [])
    actions = {e["action_id"]: e["data"] for e in history if e.get("type") == "action"}
    observations = {e["action_id"]: e["data"] for e in history if e.get("type") == "observation" and e.get("action_id") in actions}
    results = {}

    def emit(name, status, expected, actual, evidence, reason):
        results[name] = dict(status=status, expected=expected, actual=actual, evidence=evidence, reason=reason)

    def check_refs(entry):
        values = flatten(entry.get("actual", {}))
        covered, checked = set(), []
        for ref in entry.get("evidence", []):
            path, aid = ref.get("claim"), ref.get("action_id")
            obs = observations.get(aid, {})
            valid = False
            if path in values and obs.get("status") == "ok" and actions.get(aid, {}).get("action") in ("run_sql", "inspect_data"):
                try:
                    column = obs["columns"].index(ref["column"])
                    cell = obs["rows"][ref["row"]][column]
                    valid = type(ref["row"]) is int and ref["row"] >= 0 and close(cell, values[path])
                except (KeyError, ValueError, IndexError, TypeError):
                    pass
                # 方法/公式/期间集不能通过单值匹配证明：显式人工核对，不接受模型自认证。
                review = ref.get("manual_review", {})
                if (review.get("passed") is True and review.get("reviewer") and review.get("reason")
                        and ref.get("kind") == "manual" and review.get("scope") == "external_human"):
                    valid = True
            if valid:
                covered.add(path)
            checked.append({**ref, "verified": valid})
        return covered, checked

    all_covered, all_claims, all_checks = 0, 0, []
    for name, expected in expectations(truth).items():
        entry = assessment.get(name, {})
        actual = entry.get("actual", {})
        exp, act = flatten(expected), flatten(actual)
        covered, checked = check_refs(entry)
        all_covered += len(covered)
        all_claims += len(act)
        all_checks.extend(checked)
        wrong = [k for k in exp if k in act and not close(act[k], exp[k])]
        missing = [k for k in exp if k not in act]
        unsupported = [k for k in exp if k in act and k not in covered]
        if wrong:
            status = "PARTIAL" if name == "drill_down_quality" else "FAIL"
            reason = "与标准答案不符：" + ", ".join(wrong)
            if name == "drill_down_quality":
                reason += "；其他合理下钻路线需人工复核，不直接判错"
        elif missing or unsupported:
            status = "PARTIAL"
            reason = f"缺少字段 {missing}；缺少已验证证据 {unsupported}"
        else:
            status, reason = "PASS", "数值/口径一致，且有可核对的证据引用"
        emit(name, status, expected, actual, checked, reason)

    grounding = "PASS" if all_claims and all_covered == all_claims else "PARTIAL"
    emit("evidence_grounding", grounding, "每项事实可追溯至成功Tool Observation或外部人工复核",
         {"claims": all_claims, "verified": all_covered}, all_checks, "仅匹配答案不等于证据；未标注的自由文本不自动认证")
    statements = assessment.get("statements", [])
    bad = [s for s in statements if s.get("kind") == "evidence" and s.get("causal") is True and s.get("supported") is not True]
    review = assessment.get("hypothesis_review", {})
    reviewed = review.get("reviewer") and review.get("scope") == "external_human" and review.get("complete") is True
    hypotheses_ok = all(s.get("kind") != "hypothesis" or s.get("validation_needed") for s in statements)
    status = "FAIL" if bad else "PASS" if statements and reviewed and hypotheses_ok else "PARTIAL"
    emit("hypothesis_discipline", status, "未证实原因不得写为事实；假设需标明验证方法", statements, review,
         "存在无证据因果断言" if bad else "自由文本因果语义需要完整人工复核，不能靠关键词宣告PASS")

    sql_actions = [(aid, a["arguments"].get("query", "")) for aid, a in actions.items() if a.get("action") == "run_sql"]
    unsafe = []
    grain_review = assessment.get("grain_review", {})
    for aid, sql in sql_actions:
        # 保守静态筛查，不执行候选SQL；字符串常量/注释不作为写操作证据。
        stripped = re.sub(r"'(?:''|[^'])*'|--[^\n]*|/\*[\s\S]*?\*/", " ", sql)
        if re.search(r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|ATTACH|PRAGMA|REPLACE)\b", stripped, re.I) or not re.match(r"\s*(SELECT|WITH)\b", stripped, re.I):
            unsafe.append(aid)
    grain_ok = (grain_review.get("scope") == "external_human" and grain_review.get("reviewer")
                and grain_review.get("reason") and grain_review.get("passed") is True
                and set(grain_review.get("action_ids", [])) == {a for a, _ in sql_actions})
    safety = "FAIL" if unsafe or grain_review.get("passed") is False else "PASS" if sql_actions and grain_ok else "PARTIAL"
    emit("tool_safety", safety, "只读SQL且所有JOIN粒度安全", {"sql_action_ids": [a for a,_ in sql_actions], "unsafe": unsafe}, grain_review,
         "静态筛查不能证明复杂SQL的JOIN安全；PASS需逐查询外部人工粒度复核")

    finish = any(a.get("action") == "finish" for a in actions.values())
    completed = run.get("status") == "finished" and finish and bool(run.get("answer", "").strip())
    essential = [results[n]["status"] for n in NAMES[:6]]
    status = "FAIL" if not completed else "PASS" if all(s == "PASS" for s in essential) and grounding == "PASS" and results["hypothesis_discipline"]["status"] == "PASS" and safety == "PASS" else "PARTIAL"
    emit("task_completion", status, "完成有证据的归因报告并finish", {"status": run.get("status"), "answer": run.get("answer"), "finish": finish}, [],
         "未完成业务回答" if not completed else "执行结束不等于分析完整；结合各项评审结果")
    return {"evaluation_version": 1, "mode": "offline_structured_review", "dimensions": results,
            "counts": {s: sum(r["status"] == s for r in results.values()) for s in ("PASS", "FAIL", "PARTIAL")},
            "limitations": "人工标注不是模型自报。未实现自由文本自动语义判分、SQL完整解析或Observation真实性认证；使用可信本地trace，答案隔离于Planner。"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", required=True)
    parser.add_argument("--assessment")
    parser.add_argument("--truth", default="output/reports/gmv_ground_truth_summary.json")
    parser.add_argument("--output", default="output/reports/root_cause_eval.json")
    args = parser.parse_args()
    def path(value):
        resolved = (ROOT / value).resolve()
        if not resolved.is_relative_to(ROOT):
            raise ValueError("评测文件必须位于项目目录内")
        return resolved
    read = lambda value: json.loads(path(value).read_text(encoding="utf-8"))
    result = evaluate(read(args.run), read(args.truth), read(args.assessment) if args.assessment else None)
    path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["counts"]))


if __name__ == "__main__":
    main()
