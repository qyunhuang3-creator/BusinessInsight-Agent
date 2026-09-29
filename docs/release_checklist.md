# Portfolio Delivery Checklist

本轮仅做交付审计与文档整理，不增加 Agent/业务分析能力，不执行真实 LLM 请求。

## 已验收的项目内容

- [x] README：首屏展示业务问题、确定性结论、技术能力和一条命令入口。
- [x] Offline Demo：无需 Key、原始 CSV、数据库或第三方依赖；提交白名单包含必需的保存证据。
- [x] Final Report：公开可读 Markdown，事实可追溯，假设与限制分离。
- [x] Tableau Dashboard：作者的本地原件已完成；公开副本仅去掉绝对连接目录，XML 差异与同目录 CSV 引用通过检查。
- [x] Skill：可复用分析方法，不包含案例答案。
- [x] MCP：官方 SDK 本地 stdio；未宣称生产部署。
- [x] Eval：十维 PASS/PARTIAL/FAIL，Ground Truth 与 Planner 隔离。
- [x] Tests：99 项本地离线测试通过，无跳过；完整日志留在本地 output/demo/demo_tests.txt。
- [x] Secrets scan：全项目字节扫描和本地凭据精确比较完成；真实配置凭据仅在被排除的 .env 中命中，公开候选中未发现匹配凭据。
- [x] .gitignore：排除密钥、环境、缓存、数据库、原始 CSV、调试日志；成果按文件白名单放行。
- [x] Data instructions：Kaggle/Olist 来源、许可、原始数据准备和离线不依赖原始数据已说明。
- [x] Limitations：保留 Provider 429、复杂 Agent 未完成、报告语义映射与 MCP 边界。

## 发布操作仍需确认

- [ ] 实际 Git 暂存区和历史审查：当前目录没有 .git，git status 返回 not a git repository；本次未初始化仓库、提交或推送，无法认证不存在历史密钥。
- [ ] 公开 Tableau 副本在另一台机器的 Tableau 2025.1 中打开检查。它只有目录属性变化，但不能用 XML 检查代替 UI 验收。
- [ ] 作者选择项目代码的软件许可（数据归属与数据许可已在 DATA_NOTICE.md 单列）。

## 建议 commit 的范围

根目录 README.md、.gitignore、DATA_NOTICE.md、requirements.txt、requirements-mcp.txt；src/、scripts/、skills/、evals/、tests/、docs/ 的源代码与文档；以及 .gitignore 明确列出的精选 output 文件。依照白名单正常 git add，禁止使用 git add -f 整个目录。

公开成果包含业务报告、Ground Truth 聚合报告/摘要/SQL与贡献 CSV、最终离线 Eval、Demo 摘要/安全轨迹、Tableau README/五张聚合 CSV/公开 Workbook。发布包不包含客户样本或原始 API 交互日志。

## 绝对不提交

.env、任何真实凭据、.venv/、__pycache__/、缓存、临时文件、data/ 中原始 CSV 与 olist.db、Kaggle 下载凭据、本机路径的原 Tableau Workbook、全量 profiling 样本与原始 API 日志。不要直接上传整个项目文件夹 ZIP；应从审查过的 Git 内容制作发布包。

## 原件与公开副本

- 本地原件：output/tableau/BusinessInsight_Dashboard.twb，440,929 bytes，包含五处本机绝对连接目录，排除提交，原文件未改动。
- 公开副本：output/tableau/BusinessInsight_Dashboard_public.twb，440,634 bytes，只将五处 directory 改为 `.`；密码/用户名/服务器认证字段无非空值，未嵌入数据库。
- 原始九张 CSV 不提交；SQLite 159,748,096 bytes 不提交。公开聚合数据的来源和条件见 DATA_NOTICE.md。

## 保留在本地、不建议公开的中间产物

以下不是本轮删除项；可能有复盘价值，已由 ignore 规则隔离：

- output/reports/data_inspection.*、compact_schema.json、iteration5_compact_context.json：profiling/上下文调试结果，可能含样本或本机路径。
- gmv_agent_demo.json、final_agent_demo.json：历史原始运行轨迹；保留失败事实，公开 README 与脱敏评测摘要即可。
- schema_context_metrics.json、history_compaction_metrics.json、iteration5_compact_context.json：优化过程测量。
- source_hashes_before.json、report_generation_protected_hashes.json、各阶段 *_tests.txt：本地验收记录，可能含机器路径。
- output/demo/delivery_secret_scan.json、delivery_audit.json：本地安全审计元信息。
- __pycache__/、.pyc：可随时重建的缓存。当前无需清理；不影响交付。

现有 gmv_ground_truth.py、demo_business_report.py、demo_mcp.py 与统一 CLI 各司其职，不视为应删除的重复脚本。python_tool.py 是未实现的预留文件，不作为已完成功能宣传。

## 验证含义

原项目运行 Offline Demo 与完整测试；另用临时 Git 元数据计算可提交文件清单，复制到项目内临时目录，去掉 .env/数据库/原始数据/虚拟环境后，以 Python `-S` 运行 Offline Demo 验证交付独立性。临时验证不是实际提交，也不证明旧仓库历史安全。完整99项数据测试仍需本地数据与依赖。

Secrets scan 是凭据精确比较和常见模式检测，不是对未知格式、加密内容或未来更改的绝对保证。第三方依赖出现格式常量/编码内容的模式命中均处于被排除的 .venv 内，未作为业务密钥公开。真正 git add 后仍应检查暂存 diff，开启 GitHub secret scanning。
