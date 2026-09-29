# BusinessInsight Agent：两分钟作品导览

**一句话：将电商 GMV 异动分析与有证据约束的 AI Agent 工程结合，交付可核对的业务结论、报告和 Tableau 可视化。**

## 业务问题与发现

问题：Olist 是否存在 GMV 明显下降的完整月份，主要贡献来自哪里？

确定性 SQL/Python 分析先排除不可比较月份，再发现 **2017-11 → 2017-12** 的 Product GMV 从 **1,010,271.37** 降至 **743,914.17**，环比 **−26.36%**。订单量贡献净下降的 **91.87%**，AOV 贡献 **8.13%**。

品类、客户州、卖家三个视角的最大下降成员分别为 `cama_mesa_banho`、`SP` 和报告所列卖家。SP 贡献总体下降 **29.85%**，因此进一步下钻到 SP 内的品类与卖家。贡献不是因果证明；流量、促销、库存解释需额外数据验证。

## 看什么

- [Final Business Report](../output/reports/agent_business_report.md)：从摘要到指标分解、维度贡献、下钻、证据与后续调查建议。
- [Ground Truth](../output/reports/gmv_ground_truth.md)：口径、月份覆盖、对账与完整业务案例。
- [Demo Summary](../output/demo/demo_summary.md)：面试演示流程和核心结果。
- [Tableau Dashboard 公开副本](../output/tableau/BusinessInsight_Dashboard_public.twb)：在 Tableau 2025.1 打开；五张 CSV 位于同目录。公开副本仅替换本机绝对目录，尚待在另一台机器做 UI 打开检查；必要时重新定位同目录 CSV。原 Dashboard 已由作者完成并验证，未被修改。

## 一条命令体验

在项目根目录使用 Python 3.11.6：

```powershell
python scripts/run_business_insight_demo.py --mode offline
```

无需 API Key、数据库、Kaggle 原始 CSV 或 pip 安装。仓库白名单包含回放所需的结构化摘要。终端依次展示七阶段，并生成报告与 Demo Trace。此模式是**已验证分析的确定性回放**，不是实时 LLM 推理。

## Agent 工程看点

`问题 → Planner + Skill → Agent Loop → 只读 SQL / Data Profiler → Observation → Context → Re-planning → Report`

包含 Structured Output、Action Validation、Compact Schema、历史压缩、SQL 错误恢复、只读 authorizer、本地 MCP Client/Server，以及与 Planner 隔离的十维 Eval。精确指标由 SQL/Python 计算，模型负责规划。报告层验证 Evidence 来源并在模型不可用时确定性降级。

## 真实性与限制

- 本地确定性业务案例、离线 Demo 与 99 项测试已验证；原 Tableau Dashboard 由作者在 Tableau 中构建，不是 Agent 自动生成。
- 最终真实复杂 Agent Demo 在第二轮遇到 Provider HTTP 429，未完成；未用 Ground Truth 补写 Agent 答案。
- 实时 Agent 的自动语义证据映射仍有限；MCP 是本地 stdio 演示，不是生产级系统。
- 原始数据与数据库不随仓库分发；完整数据工具/MCP测试需要按 README 下载数据。数据来源及使用条件见 [Data Notice](../DATA_NOTICE.md)。
