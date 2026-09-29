"""确定性 Olist GMV 标准答案；只读 SQLite，无网络/LLM 调用。

从项目根目录运行 .venv/Scripts/python.exe -X utf8 scripts/gmv_ground_truth.py
金额按每条明细四舍五入到分后整数累计，避免浮点 SUM 的累积误差。
"""
from pathlib import Path
import calendar
import hashlib
import json
import sqlite3
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output" / "reports"


def md(frame):
    def fmt(v):
        if pd.isna(v):
            return "—"
        if isinstance(v, float):
            return f"{v:,.4f}"
        return str(v).replace("|", "\\|").replace("\n", " ")
    return "\n".join(["| " + " | ".join(map(str, frame.columns)) + " |",
                      "| " + " | ".join("---" for _ in frame.columns) + " |"] +
                     ["| " + " | ".join(fmt(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)])


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "data").glob("*.csv"))}
    connection = sqlite3.connect((ROOT / "data" / "olist.db").as_uri() + "?mode=ro", uri=True)
    connection.execute("PRAGMA query_only=ON")
    connection.execute("PRAGMA temp_store=MEMORY")
    queries = {}

    def query(name, sql, params=()):
        queries[name] = {"sql": sql, "parameters": list(params)}
        return pd.read_sql_query(sql, connection, params=params)

    orders = query("order_quality", """SELECT COUNT(*) rows_n, COUNT(DISTINCT order_id) distinct_ids,
        SUM(order_id IS NULL) null_ids, SUM(order_purchase_timestamp IS NULL) missing_time,
        SUM(date(order_purchase_timestamp) IS NULL) invalid_time FROM orders""")
    item_quality = query("item_quality", """SELECT COUNT(*) rows_n, SUM(price IS NULL) missing_price,
        SUM(price<0) negative_price, SUM(price=0) zero_price,
        SUM(order_id IS NULL OR order_item_id IS NULL) null_keys,
        SUM(ABS(price*100-ROUND(price*100))>0.00001) non_cent_prices FROM order_items""")
    duplicate_items = query("item_duplicate_keys", """SELECT COUNT(*) n FROM
        (SELECT order_id,order_item_id FROM order_items GROUP BY 1,2 HAVING COUNT(*)>1)""")
    duplicate_payments = query("payment_duplicate_keys", """SELECT COUNT(*) n FROM
        (SELECT order_id,payment_sequential FROM payments GROUP BY 1,2 HAVING COUNT(*)>1)""")
    quality = {"orders": orders.to_dict("records")[0], "order_items": item_quality.to_dict("records")[0],
               "duplicate_item_key_groups": int(duplicate_items.iloc[0, 0]),
               "duplicate_payment_key_groups": int(duplicate_payments.iloc[0, 0])}
    assert orders.iloc[0].rows_n == orders.iloc[0].distinct_ids
    assert orders.iloc[0].null_ids == 0 and orders.iloc[0].invalid_time == 0
    assert item_quality.iloc[0].null_keys == 0 and item_quality.iloc[0].non_cent_prices == 0
    assert duplicate_items.iloc[0, 0] == 0
    for table, key in (("products", "product_id"), ("customers", "customer_id"), ("sellers", "seller_id")):
        counts = query(f"{table}_unique", f"SELECT COUNT(*) n,COUNT(DISTINCT {key}) distinct_n FROM {table}")
        assert counts.iloc[0, 0] == counts.iloc[0, 1]
    quality["orphan_items"] = int(query("orphans", """SELECT COUNT(*) n FROM order_items i LEFT JOIN orders o
        ON i.order_id=o.order_id WHERE o.order_id IS NULL""").iloc[0, 0])
    assert quality["orphan_items"] == 0

    daily = query("daily_coverage", """SELECT date(o.order_purchase_timestamp) day, COUNT(*) all_orders,
        SUM(EXISTS(SELECT 1 FROM order_items i WHERE i.order_id=o.order_id AND i.price IS NOT NULL AND i.price>=0)) valid_orders
        FROM orders o GROUP BY 1 ORDER BY 1""")
    daily["day"] = pd.to_datetime(daily["day"])
    dates = pd.date_range(daily.day.min().replace(day=1), daily.day.max() + pd.offsets.MonthEnd(0))
    daily = daily.set_index("day").reindex(dates, fill_value=0).rename_axis("day").reset_index()
    daily["month"] = daily.day.dt.strftime("%Y-%m")
    coverage = []
    for month, group in daily.groupby("month"):
        all_days = group.loc[group.all_orders > 0, "day"]
        valid_days = group.loc[group.valid_orders > 0, "day"]
        longest, streak = 0, 0
        for count in group.valid_orders:
            streak = streak + 1 if count == 0 else 0
            longest = max(longest, streak)
        coverage.append({"month": month, "calendar_days": len(group), "covered_days": len(all_days),
                         "first_order_date": str(all_days.min().date()) if len(all_days) else None,
                         "last_order_date": str(all_days.max().date()) if len(all_days) else None,
                         "all_orders": int(group.all_orders.sum()), "valid_order_days": len(valid_days),
                         "first_valid_date": str(valid_days.min().date()) if len(valid_days) else None,
                         "last_valid_date": str(valid_days.max().date()) if len(valid_days) else None,
                         "max_zero_valid_day_streak": longest,
                         "comparable": len(all_days) == len(group) and len(valid_days) == len(group)})
    coverage = pd.DataFrame(coverage)

    base = query("analysis_base", """SELECT o.order_id, o.order_status,
        strftime('%Y-%m',o.order_purchase_timestamp) month,
        i.order_item_id, CAST(ROUND(i.price*100) AS INTEGER) price_cents,
        COALESCE(NULLIF(TRIM(p.product_category_name),''),'Unknown') product_category,
        COALESCE(NULLIF(TRIM(c.customer_state),''),'Unknown') customer_state,
        COALESCE(NULLIF(TRIM(i.seller_id),''),'Unknown') seller,
        p.product_id matched_product,c.customer_id matched_customer,s.seller_id matched_seller
        FROM orders o JOIN order_items i ON i.order_id=o.order_id
        LEFT JOIN products p ON p.product_id=i.product_id
        LEFT JOIN customers c ON c.customer_id=o.customer_id
        LEFT JOIN sellers s ON s.seller_id=i.seller_id
        WHERE i.price IS NOT NULL AND i.price>=0 AND date(o.order_purchase_timestamp) IS NOT NULL""")
    baseline = query("join_reconciliation", """SELECT COUNT(*) n,SUM(CAST(ROUND(price*100) AS INTEGER)) cents
        FROM order_items WHERE price IS NOT NULL AND price>=0""")
    assert len(base) == int(baseline.iloc[0, 0])
    assert int(base.price_cents.sum()) == int(baseline.iloc[0, 1])
    quality["join_rows"] = len(base)
    quality["join_cents"] = int(base.price_cents.sum())
    quality["unmatched_dimensions"] = {c: int(base[c].isna().sum()) for c in ("matched_product", "matched_customer", "matched_seller")}
    quality["unknown_category_items"] = int((base.product_category == "Unknown").sum())
    quality["orders_without_valid_items"] = int(orders.iloc[0].rows_n - base.order_id.nunique())
    monthly = base.groupby("month").agg(gmv_cents=("price_cents", "sum"), order_volume=("order_id", "nunique")).reset_index()
    monthly = coverage.merge(monthly, on="month", how="left")
    monthly[["gmv_cents", "order_volume"]] = monthly[["gmv_cents", "order_volume"]].fillna(0).astype("int64")
    monthly["gmv"] = monthly.gmv_cents / 100
    monthly["aov"] = monthly.gmv / monthly.order_volume.replace(0, float("nan"))
    monthly["comparison_eligible"] = monthly.comparable & monthly.comparable.shift(1, fill_value=False)
    for metric in ("gmv", "order_volume", "aov"):
        monthly[metric + "_mom_pct"] = ((monthly[metric] / monthly[metric].shift(1) - 1) * 100).where(monthly.comparison_eligible)
    monthly["gmv_change"] = monthly.gmv.diff().where(monthly.comparison_eligible)
    monthly["candidate_decline"] = monthly.comparison_eligible & (monthly.gmv_mom_pct <= -10)
    candidates = monthly[monthly.candidate_decline].sort_values("gmv_change")
    assert not candidates.empty, "没有满足规则的候选月份，不应继续归因"
    current = candidates.iloc[0]
    previous_month = str(pd.Period(current.month, freq="M") - 1)
    previous = monthly[monthly.month == previous_month].iloc[0]
    delta_cents = int(current.gmv_cents - previous.gmv_cents)
    delta = delta_cents / 100
    volume_effect = (current.order_volume - previous.order_volume) * (current.aov + previous.aov) / 2
    aov_effect = (current.aov - previous.aov) * (current.order_volume + previous.order_volume) / 2
    assert abs(volume_effect + aov_effect - delta) < 1e-7

    pair = base[base.month.isin([previous_month, current.month])]

    def contributions(data, dimension, denominator=delta_cents):
        pivot = data.groupby([dimension, "month"]).price_cents.sum().unstack(fill_value=0)
        for month in (previous_month, current.month):
            if month not in pivot:
                pivot[month] = 0
        result = pd.DataFrame({"member": pivot.index, "previous_cents": pivot[previous_month].values,
                               "current_cents": pivot[current.month].values})
        result["change_cents"] = result.current_cents - result.previous_cents
        result["dimension"] = dimension
        result["previous_month"] = previous_month
        result["current_month"] = current.month
        result["previous_gmv"] = result.previous_cents / 100
        result["current_gmv"] = result.current_cents / 100
        result["absolute_change"] = result.change_cents / 100
        result["growth_rate_pct"] = (result.current_cents / result.previous_cents.replace(0, float("nan")) - 1) * 100
        result["contribution_to_total_decline_pct"] = result.change_cents / denominator * 100
        result["presence"] = "both"
        result.loc[result.previous_cents == 0, "presence"] = "current_only"
        result.loc[result.current_cents == 0, "presence"] = "previous_only"
        return result.sort_values(["change_cents", "member"]).reset_index(drop=True)

    dimensions = {d: contributions(pair, d) for d in ("product_category", "customer_state", "seller")}
    for table in dimensions.values():
        assert int(table.change_cents.sum()) == delta_cents
    # 对三个解释视角中下降金额最大的单个成员下钻，不提前指定维度。
    selected_dimension = min(dimensions, key=lambda d: dimensions[d].iloc[0].change_cents)
    selected = dimensions[selected_dimension].iloc[0]
    subset = pair[pair[selected_dimension] == selected.member]
    drill = {d: contributions(subset, d) for d in dimensions if d != selected_dimension}
    for table in drill.values():
        assert int(table.change_cents.sum()) == int(selected.change_cents)
        table["contribution_to_parent_decline_pct"] = table.change_cents / selected.change_cents * 100
        table["parent_dimension"] = selected_dimension
        table["parent_member"] = selected.member

    status = pair.groupby(["order_status", "month"]).agg(gmv_cents=("price_cents", "sum"), orders=("order_id", "nunique")).reset_index()
    sensitivity = []
    for label, frame in [("all_valid_item_orders", pair), ("exclude_canceled_unavailable", pair[~pair.order_status.isin(["canceled", "unavailable"])]), ("delivered_only", pair[pair.order_status == "delivered"])]:
        values = frame.groupby("month").price_cents.sum()
        sensitivity.append({"scope": label, "previous_gmv": values[previous_month]/100,
                            "current_gmv": values[current.month]/100,
                            "change": (values[current.month]-values[previous_month])/100,
                            "mom_pct": (values[current.month]/values[previous_month]-1)*100})
    sensitivity = pd.DataFrame(sensitivity)

    def export(frame, name):
        frame.to_csv(OUT / name, index=False, encoding="utf-8-sig", float_format="%.8f")
    export(monthly, "monthly_metrics.csv")
    export(pd.concat(dimensions.values(), ignore_index=True), "dimension_contribution.csv")
    export(pd.concat(drill.values(), ignore_index=True), "gmv_drill_down.csv")
    export(daily, "gmv_daily_coverage.csv")
    export(coverage, "gmv_month_coverage.csv")
    export(sensitivity, "gmv_status_sensitivity.csv")

    summary = {"previous_month": previous_month, "current_month": current.month,
               "previous_gmv": float(previous.gmv), "current_gmv": float(current.gmv), "gmv_change": delta,
               "gmv_mom_pct": float(current.gmv_mom_pct), "previous_orders": int(previous.order_volume),
               "current_orders": int(current.order_volume), "order_mom_pct": float(current.order_volume_mom_pct),
               "previous_aov": float(previous.aov), "current_aov": float(current.aov), "aov_mom_pct": float(current.aov_mom_pct),
               "volume_effect": float(volume_effect), "volume_contribution_pct": float(volume_effect/delta*100),
               "aov_effect": float(aov_effect), "aov_contribution_pct": float(aov_effect/delta*100),
               "top_dimensions": {d: t.iloc[0].to_dict() for d,t in dimensions.items()},
               "drill_parent": selected_dimension, "drill_member": selected.member,
               "drill_top": {d: t.iloc[0].to_dict() for d,t in drill.items()},
               "comparable_months": monthly.loc[monthly.comparable,"month"].tolist(),
               "candidate_months": candidates.month.tolist(), "quality": quality}
    sections = ["# Olist Product GMV 异动 Ground Truth\n",
        "本报告由项目 SQLite 的确定性 SQL/Python 计算生成；没有调用 LLM。标准答案针对下述明确口径，数值已进行键、JOIN、分解及分组对账。不能视为数据抽取完整性或因果关系的外部证明。\n",
        "## 1. 指标与范围\n",
        "Product GMV = SUM(order_items.price)，不含运费，不使用 payment_value。有效明细为 order_id 可关联、price 非空且 >=0、购买日期可解析；本数据没有空/负/零价格。Order Volume 是同一范围的去重 order_id；AOV=GMV/Order Volume。购买时间按原始本地时间字符串的自然月归属，不转换时区。\n",
        "主分析保留所有订单状态中有有效明细的订单，衡量创建订单商品金额，不是收入、净成交或退款后GMV。另提供剔除 canceled/unavailable 与 delivered-only 敏感性结果；历史状态是数据快照状态。金额按每条价格转整数分精确累计；AOV与贡献计算使用未舍入值。CSV 比例字段单位为百分数，空值表示不可比较或零基期。\n",
        "## 2. 数据质量与可比较月份\n",
        f"原始订单时间跨度：{daily.loc[daily.all_orders>0,'day'].min().date()} 至 {daily.loc[daily.all_orders>0,'day'].max().date()}；全范围包括无订单的自然日与月份。\n",
        "规则：订单记录与有效明细订单在该自然月每一天均有记录，才作为可比较月；不满足者保守排除。MoM 仅在当前与紧邻上一个自然月均可比较时计算。该规则是覆盖代理，不能排除每天均存在的漏抽数据，也可能排除真正零交易日的月份。\n",
        f"可比较范围：{summary['comparable_months'][0]} 至 {summary['comparable_months'][-1]}。内部无零订单/零有效明细订单日断档。2018-08虽覆盖31个订单日，但有效明细仅覆盖29天，故排除；2018-09/10及稀疏首部月份同样排除。2016-11无订单也在表中明确保留。\n",
        md(coverage), "\n质量检查：\n```json\n" + json.dumps(quality,ensure_ascii=False,indent=2) + "\n```\n",
        "orders 主键、order_items 复合键及 products/customers/sellers 关联键通过唯一性检查。LEFT JOIN 维度前后行数及整数分总额相等；未知类别保留 Unknown。未连接 payments，避免 M×N 金额膨胀。\n",
        "## 3. 完整可比较月份趋势\n",
        md(monthly.loc[monthly.comparable,["month","gmv","gmv_mom_pct","order_volume","order_volume_mom_pct","aov","aov_mom_pct"]]),
        "\n首个可比较月无合格前月，MoM 留空。完整原始月份与排除标记见 monthly_metrics.csv。\n",
        "## 4. 候选下降月份（MoM <= -10%，按绝对下降金额排序）\n",
        md(candidates[["month","gmv","gmv_change","gmv_mom_pct","order_volume_mom_pct","aov_mom_pct"]]),
        f"\n选择 {previous_month} → {current.month}，依据最大绝对 GMV 下降，不按最低增长率或尾部月份预选。\n",
        "## 5. GMV 对称分解\n",
        f"GMV：{previous.gmv:,.2f} → {current.gmv:,.2f}，变化 {delta:,.2f}（{current.gmv_mom_pct:.4f}%）。订单量：{int(previous.order_volume):,} → {int(current.order_volume):,}（{current.order_volume_mom_pct:.4f}%）。AOV：{previous.aov:.6f} → {current.aov:.6f}（{current.aov_mom_pct:.4f}%）。\n",
        f"订单量贡献=(V1−V0)×(A1+A0)/2 = {volume_effect:,.6f}，占净下降 {volume_effect/delta*100:.4f}%。AOV贡献=(A1−A0)×(V1+V0)/2 = {aov_effect:,.6f}，占 {aov_effect/delta*100:.4f}%。两项之和 {volume_effect+aov_effect:,.6f}，与总变化误差 {volume_effect+aov_effect-delta:.10f}。\n",
        f"日均订单变化：{previous.order_volume/calendar.monthrange(int(previous_month[:4]),int(previous_month[5:]))[1]:.4f} → {current.order_volume/calendar.monthrange(int(current.month[:4]),int(current.month[5:]))[1]:.4f}，须结合自然月天数解读。\n",
        "## 6. 维度贡献\n",
        "contribution = 该组GMV变化 / 总GMV变化。总体下降时，下降组为正贡献，增长组为负的抵消贡献；可超过100%。三个维度是平行解释视角，不能跨维度相加。成员取两期并集，新增成员增长率留空、消失成员为−100%，未知归入Unknown。\n"]
    cols = ["member","previous_gmv","current_gmv","absolute_change","growth_rate_pct","contribution_to_total_decline_pct","presence"]
    for dimension, table in dimensions.items():
        sections += [f"### {dimension}\n", "下降贡献前10：\n", md(table.head(10)[cols]),
                     "\n增长抵消前5：\n", md(table.sort_values("change_cents",ascending=False).head(5)[cols]),
                     f"\n对账：{len(table)}组的变化之和={table.absolute_change.sum():,.2f}；整数分与总体变化完全相等。上期独有{int((table.presence=='previous_only').sum())}组，当期独有{int((table.presence=='current_only').sum())}组。\n"]
    sections += ["## 7. 数据驱动 Drill Down\n",
                 f"比较三个维度中下降最大的单个成员，选择 {selected_dimension}={selected.member}，变化 {selected.absolute_change:,.2f}，贡献总体净下降 {selected.contribution_to_total_decline_pct:.4f}%。这仅用于定位集中度，不意味着该维度更有因果解释力。\n"]
    for dimension, table in drill.items():
        sections += [f"### {selected_dimension} → {dimension}\n", md(table.head(10)[cols+["contribution_to_parent_decline_pct"]]),
                     f"\n该下钻分组变化和={table.absolute_change.sum():,.2f}，精确对账父组。\n"]
    sections += ["## 8. 状态口径敏感性\n", md(sensitivity), "\n两期订单状态分布：\n", md(status),
        "\n## 9. Evidence\n",
        f"- 主分析月份为 {current.month}，GMV 变化 {current.gmv_mom_pct:.4f}%，按既定覆盖与下降规则筛选。\n"
        f"- 订单量贡献 {volume_effect:,.2f}，AOV贡献 {aov_effect:,.2f}；分解仅描述算术来源。\n" +
        "\n".join(f"- {d} 最大下降成员为 {t.iloc[0].member}，绝对变化 {t.iloc[0].absolute_change:,.2f}。" for d,t in dimensions.items()),
        "\n## 10. Hypothesis（待验证）\n",
        "流量减少、前月促销拉高基数、促销退坡、库存/供给变化、竞争或渠道变化都可能解释变化，但当前数据没有曝光、访问、活动、库存或竞品字段，不能确认。需结合流量漏斗、活动日历、库存与商家运营日志验证。不能仅因月份位置就断言促销是原因。\n",
        "## 11. Limitations\n",
        "- 日覆盖完整不等于抽取完整，所选窗口为保守可比较范围。首尾月份未作为业务异常。\n- GMV不含运费，不扣退款，含非交付订单；状态快照不能恢复当时状态。\n- 贡献是描述性定位，不是因果归因；维度重叠，不能相加。\n- 月份天数、季节性与历史长度影响比较；−10%是探索阈值，不是显著性检验。\n- 品类缺失保持Unknown；交易数据不包含所有流量和商家供给行为。\n",
        "## 12. 复现与验收\n",
        "运行 `.venv/Scripts/python.exe -X utf8 scripts/gmv_ground_truth.py`。数据库只读，所有源CSV哈希运行前后核对。SQL记录在 gmv_ground_truth_queries.json；机器可读答案在 gmv_ground_truth_summary.json。复核同一口径时整数分总额应完全一致，未舍入分解误差小于1e-7。\n"]
    (OUT / "gmv_ground_truth.md").write_text("\n".join(sections),encoding="utf-8")
    (OUT / "gmv_ground_truth_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=lambda x:x.item()),encoding="utf-8")
    (OUT / "gmv_ground_truth_queries.json").write_text(json.dumps(queries,ensure_ascii=False,indent=2),encoding="utf-8")
    connection.close()
    assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT / "data").glob("*.csv"))}
    (OUT / "gmv_source_hashes.json").write_text(json.dumps(hashes,indent=2),encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False,indent=2,default=lambda x:x.item()))


if __name__ == "__main__":
    main()
