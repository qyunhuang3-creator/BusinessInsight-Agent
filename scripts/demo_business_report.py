"""Offline example adapter: verified deterministic artifacts -> Evidence -> report.

Only this example knows artifact field names. Never passes Ground Truth to an
Agent/Planner. Does not execute SQL, alter source files, or call a model.
"""
import json
from pathlib import Path
from src.report_generator import generate_report

ROOT = Path(__file__).resolve().parents[1]


def example_bundle():
    source_path = ROOT / "output/reports/gmv_ground_truth_summary.json"
    data = json.loads(source_path.read_text(encoding="utf-8"))
    period = data["previous_month"] + " → " + data["current_month"]
    # Small deterministic presentation derivations, not a rerun of the analysis.
    derived = {"order_change": data["current_orders"] - data["previous_orders"],
               "aov_change": data["current_aov"] - data["previous_aov"],
               "main_driver": "Order Volume" if abs(data["volume_effect"]) > abs(data["aov_effect"]) else "AOV",
               "anomaly_status": data["current_month"] in data["candidate_months"],
               "comparable_months": ", ".join(data["comparable_months"])}
    bundle = {"question": "Olist 数据中是否存在 GMV 明显下降的完整月份？如果存在，主要由哪些因素驱动？",
        "analysis_status": "已验证确定性分析示例；不是未完成 LLM Demo 的输出",
        "origin": "existing deterministic SQL/Python analysis artifacts",
        "sources": {
            "analysis": {"status": "ok", "tool": "deterministic_python",
                "reference": "output/reports/gmv_ground_truth_summary.json",
                "query": "scripts/gmv_ground_truth.py；SQL清单 output/reports/gmv_ground_truth_queries.json",
                "data": data},
            "derived": {"status": "ok", "tool": "deterministic_python",
                "reference": "scripts/demo_business_report.py::example_bundle",
                "query": "change=current-previous; main_driver=argmax(abs(volume_effect),abs(aov_effect)); anomaly=current_month in candidate_months; comparable_months=join(existing list)",
                "data": derived}},
        "evidence": [],
        "hypotheses": {"traffic": "访问量或转化率下降可能影响订单量，需要漏斗数据验证。",
                       "promotion": "前期促销拉高基数或活动变化可能影响比较，需要活动日历验证；当前交易数据不能确认。",
                       "supply": "库存或卖家可售状态变化可能影响供给，需要库存和商家日志验证。"},
        "limitations": {"coverage": "每日有订单仅是期间可比较性的代理，不能证明抽取完整。",
            "scope": "Product GMV 不含运费、不扣退款，保留所有状态的有效明细订单，不等于收入。",
            "causality": "指标分解是算术归因，维度贡献是描述性定位；不同维度不能相加或解释为因果。",
            "time": "自然月天数、季节性与订单状态快照影响业务解释。",
            "provenance": "来源字段一致性已经校验；标签、口径和事实语义仍依赖上游分析及人工复核。"},
        "recommended_next_checks": {"traffic": "检查访问量、转化率与渠道漏斗。",
            "promotion": "核对活动日历与折扣变化。", "inventory": "检查重点地区相关品类的库存与缺货记录。",
            "seller": "复核下降贡献较大卖家的可售状态、商品供给与运营日志。"}}

    def add(eid, section, metric, mapping, dimension="Overall", source_id="analysis"):
        source = bundle["sources"][source_id]["data"]
        def lookup(path):
            value = source
            for part in path:
                value = value[part]
            return value
        bundle["evidence"].append({"id": eid, "section": section, "metric": metric, "period": period,
            "dimension": dimension, "source_id": source_id,
            "values": {label: lookup(path) for label, path in mapping.items()}, "references": mapping})

    add("gmv", "anomaly_overview", "Product GMV 异动", {k: [k] for k in
        ("previous_month", "current_month", "previous_gmv", "current_gmv", "gmv_change", "gmv_mom_pct")})
    add("period", "anomaly_overview", "可比较性与异常状态", {k: [k] for k in
        ("anomaly_status", "comparable_months")}, source_id="derived")
    add("orders", "anomaly_overview", "Order Volume（有效明细订单）", {k: [k] for k in
        ("previous_orders", "current_orders", "order_mom_pct")})
    add("aov", "anomaly_overview", "AOV", {k: [k] for k in ("previous_aov", "current_aov", "aov_mom_pct")})
    add("changes", "anomaly_overview", "订单量与 AOV 绝对变化", {k: [k] for k in ("order_change", "aov_change")}, source_id="derived")
    add("volume", "metric_decomposition", "GMV Change → Order Volume Contribution",
        {k: [k] for k in ("volume_effect", "volume_contribution_pct")})
    add("aov_effect", "metric_decomposition", "GMV Change → AOV Contribution",
        {k: [k] for k in ("aov_effect", "aov_contribution_pct")})
    add("driver", "metric_decomposition", "主要算术驱动（不等于因果）", {"main_driver": ["main_driver"]}, source_id="derived")
    for dim in data["top_dimensions"]:
        add("top_" + dim, "dimension_attribution", "最大下降贡献：" + dim,
            {k: ["top_dimensions", dim, k] for k in
             ("member", "previous_gmv", "current_gmv", "absolute_change", "growth_rate_pct", "contribution_to_total_decline_pct")}, dim)
    for dim in data["drill_top"]:
        add("drill_" + dim, "drill_down_findings", "下钻：" + dim,
            {k: ["drill_top", dim, k] for k in
             ("parent_dimension", "parent_member", "member", "previous_gmv", "current_gmv", "absolute_change", "contribution_to_parent_decline_pct")},
            "Overall GMV → " + data["drill_parent"] + " → " + data["drill_member"] + " → " + dim)
    for e in bundle["evidence"]:
        if e["id"] == "gmv":
            e["summary_fields"] = ["previous_month", "current_month", "gmv_change", "gmv_mom_pct"]
        elif e["section"] == "dimension_attribution":
            e["summary_fields"] = ["member", "absolute_change", "contribution_to_total_decline_pct"]
    return bundle


def main():
    bundle = example_bundle()
    result = generate_report(bundle)  # No client: cannot call API.
    if result["status"] != "ok":
        raise SystemExit("Invalid evidence; no report written")
    folder = ROOT / "output/reports"
    (folder / "agent_business_report.md").write_text(result["markdown"], encoding="utf-8")
    (folder / "agent_business_report_evidence.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "agent_business_report_schema.json").write_text(json.dumps(result["schema"], ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "mode": result["mode"], "client_calls": result["client_calls"], "evidence_count": len(result["evidence"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
