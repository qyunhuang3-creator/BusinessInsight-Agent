# Root Cause Analysis 离线评测

评测与 Agent 分离：只有 `evals/root_cause_eval.py` 读取标准答案。Planner 只能通过固定路径读取方法 Skill，不读取 evals 或 output/reports。运行普通测试与评测均不需要 API。

```powershell
.\.venv\Scripts\python.exe -X utf8 -m evals.root_cause_eval --run output/reports/gmv_agent_demo.json
```

可选 `--assessment evals/my_review.json` 提供人工从 Agent 最终回答提取的评审标注。没有标注时仍可评估执行是否 finish、筛查明显写SQL；其他项返回 PARTIAL，而不是用猜测填补 Agent 答案。不能把标准答案拷贝成 Agent 的 actual。

输出十项独立结果，每项有 status（PASS/FAIL/PARTIAL）、expected、actual、evidence、reason。不合并为单一分数。金额及百分点容差默认绝对 0.02、相对 1e-5；百分比值按百分数而非小数。缺失字段/缺证据为 PARTIAL，显式错误为 FAIL。证据一致但答案不符标准答案时，正确性仍 FAIL。

## 标注格式

前六项为 metric_correctness、period_correctness、anomaly_detection、decomposition_correctness、dimension_attribution、drill_down_quality。各项的 actual 字段结构与输出的 expected 对应；不要将 expected 发送给 Agent。

每个结论字段需证据引用，例如：

```json
{
  "anomaly_detection": {
    "actual": {"gmv_change": -100.0},
    "evidence": [{"claim": "gmv_change", "action_id": 3, "row": 0, "column": "gmv_change"}]
  }
}
```

这是虚构格式示例，不是本项目标准答案。引用的 Action 必须是真实 Tool 调用，Observation 必须成功，行列必须存在，单元格必须与 actual 匹配。多步公式、期间集合与口径解释需外部人工复核：

```json
{"claim":"main_driver","action_id":3,"kind":"manual","manual_review":{
  "scope":"external_human","reviewer":"reviewer-name","passed":true,
  "reason":"已逐项核对该Observation的分解数值与结论，说明计算过程"
}}
```

人工 review 是信任边界，不能接受 Agent 自报的 review。解释性 statements 使用 `text`、`kind`（evidence/hypothesis）、`causal`、`supported`、`validation_needed`。无支持的 causal evidence 判 FAIL。hypothesis_review 需 scope=external_human、reviewer、complete=true，表示人工完整检查最终回答，不能仅凭未出现敏感关键词判PASS。

tool_safety 对轨迹做保守只读筛查；复杂CTE、注释、标识符可能需人工解释。grain_review 需 scope=external_human、reviewer、reason、passed 及覆盖全部SQL调用的 action_ids。不得为了评测执行不可信 SQL。明确 unsafe SQL 或人工 grain_review failed 判 FAIL；无人核对时 PARTIAL。

Drill-down 与标准路线不一致不自动判错：合理替代路径返回 PARTIAL 待人工复核。当前自动 PASS 只覆盖已有标准路线。自由文本实际值提取、公式证据语义、人工评审真实性和完整 SQL 静态分析尚未自动化；此 MVP 是透明、可审计的离线评测辅助器，不是通用自动裁判。

Skill 触发：下降/异常/归因/原因/驱动等问题自动附加 `skills/root-cause-analysis/SKILL.md`；订单总数等单值问题不加载。Skill 不含案例答案，不指定固定 SQL、月份或维度顺序。
