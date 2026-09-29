# Final Business Report Generation

输出层接收已完成分析中的结构化证据，不执行 SQL、不加载数据库、不读取 Ground Truth、不调用 Planner，也不从自由文本最终答案提取数字。默认离线；只有显式注入兼容 `request_json(messages, json_schema=...)` 的客户端才可能发起一次请求。当前示例和测试均不调用真实 API。

## 接口与接入边界

`generate_report(bundle, client=None)` 返回 status、mode、fallback_reason、client_calls、report、schema、evidence、markdown。无有效来源的输入返回 `invalid_evidence`，不生成伪证据报告。空 Evidence 可以生成明确标为未提供证据的基础报告。

`sources_from_context(context)` 接收 AgentContext 或其 dict，只提取成功 Tool Observation，保存 action_id 和已有 SQL。它不会恢复被 Context 截断的行、猜测 metric 标签或验证业务语义。

应用层在 Agent 运行结束后调用报告层，提供显式映射。例如某条实际成功 Observation 的首行首列是已分析指标：

```python
from src.report_generator import sources_from_context, generate_report

# run = existing_agent.run(question)  # 此处指已有结果，不要求再调用 API
sources = sources_from_context(run["context"])
source_id = "action_1"  # 选择实际存在、成功且语义匹配的 action_id
value = sources[source_id]["data"]["rows"][0][0]
bundle = {
    "question": run["context"]["user_query"],
    "analysis_status": run["status"],
    "origin": "Agent Tool Observations",
    "sources": sources,
    "evidence": [{
        "id": "observed_metric", "section": "anomaly_overview",
        "metric": "已确认口径的指标", "period": "该查询的实际期间",
        "dimension": "该查询的实际分组", "source_id": source_id,
        "values": {"value": value},
        "references": {"value": ["rows", 0, 0]},
    }],
    "hypotheses": {},
    "limitations": {"partial": "示例仅包含一项观测，不等于完整归因。"},
    "recommended_next_checks": {},
}
report = generate_report(bundle)
```

此适配不改变 Agent Loop、Action Schema、Skill、MCP 或 Eval。当前不会自动把任意 SQL 列推断成业务语义；调用方必须提交经过核对的 Evidence 映射。LLM 的 `finish.answer` 不会被当作事实来源。

## 输入合同

- question / analysis_status / origin：问题、上游运行状态和来源说明。
- sources：按 source_id 索引的可信本地来源，包含 status=ok、tool（run_sql / inspect_data / deterministic_python）、reference、data，以及可选 query/计算引用。
- evidence：每条含 id、section、metric、period、dimension、source_id、values、references。values 只能为有限数值、字符串、布尔或 null；每一个 value 都必须有指向 source.data 的路径且类型和值精确相等。可选 summary_fields 只能引用该条已有字段。
- hypotheses / limitations / recommended_next_checks：调用方提供的独立文本目录。它们不是 Evidence，不自动认证其中的业务解释。

来源包是信任边界：相等校验不能证明伪造来源真实，也不能证明错误 SQL 的业务口径正确。metric、period、dimension 标签和源 SQL 仍需上游验证/Eval 复核。报告生成器不会根据 status=ok 宣告因果结论成立。

## Structured Output Schema

`report_schema(bundle)` 生成严格 object，禁止额外字段，以下字段全部必需且为唯一字符串引用数组：

```text
executive_summary
anomaly_overview
metric_decomposition
dimension_attribution
drill_down_findings
evidence
hypotheses
limitations
recommended_next_checks
```

前六项引用验证过的 Evidence ID；后三项引用对应目录 ID。按章节生成 enum、minItems、maxItems、uniqueItems 约束；除摘要允许选取外，各章节必须完整保留原输入引用，不能将 Hypothesis 移入 Evidence。`validate_report` 对该受限 JSON Schema 方言进行完整检查，不是通用 JSON Schema 引擎。

MVP 选择保守的 **reference-only narrative**：LLM 只能组织、选择摘要和调整引用顺序，不能自由撰写新业务事实。Markdown 由固定模板解析引用后渲染，所有精确数字只取自验证过的 values。没有依靠正则寻找自然语言中的数字，也不允许 LLM 修改金额、贡献率、期间或维度值。输入中的正常数字保持原精度；更丰富的自由文本叙述未在本阶段开放。

## Deterministic Fallback

默认无需客户端直接生成基础报告。显式客户端遇到 429、provider error、timeout、不可用、空结果或非法结构时，仅调用一次，然后使用同一已验证 Evidence 的完整确定性报告。不记录原始异常文本，避免泄露远端敏感内容。

核心数字、所有 Evidence、来源路径和输入中的限制不丢失；缺少部分分析就标明缺失，不用 Ground Truth 补齐。报告成功仅表示输出成功，不意味着上游分析完成。已有 API 错误不会触发重新查询或连续重试。

## 真实数据示例（明确与 Agent Demo 分开）

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m scripts.demo_business_report
```

脚本读取已有确定性结构化摘要，将字段映射为 Evidence，再调用通用生成器。只有示例适配脚本了解该摘要文件；核心模块不读取报告或标准答案。订单量/AOV 差值与主要算术驱动是适配器对已有汇总值的简单确定性派生，记录公式引用，不重跑原始交易分析。

生成 `output/reports/agent_business_report.md`、对应 `agent_business_report_evidence.json` 和 `agent_business_report_schema.json`。这些输出明确标为确定性分析示例，不伪装成此前 429 中断的 LLM 运行结果。Ground Truth 只用于本离线示例和验收，不传给 Planner。

报告章节：Executive Summary、Anomaly Overview、Metric Decomposition、Dimension Attribution、Drill-down Findings、Evidence、Hypotheses、Limitations、Recommended Next Checks。
