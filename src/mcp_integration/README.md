# BusinessInsight MCP（最小本地集成）

MCP 将工具发现、输入 Schema 和跨进程调用标准化。普通 Tool Calling 可以直接调用 Python 函数；这里真实使用官方 SDK 的初始化、tools/list、tools/call 和 stdio 传输。MCP 不负责业务规划，也不需要 LLM。

```text
BusinessInsightAgent（现有循环，Demo 用 MockPlanner）
  → 注入 Tool Registry → MCP Client → stdio MCP Server
  → 原 inspect_data / run_sql → structuredContent → 原 Context
```

默认 Agent Registry 不变。通过 client.tool_registry() 显式启用 MCP；同步适配器每次调用启动一个子进程，便于演示，不是生产连接池。不在已有 asyncio 事件循环中调用同步适配器；异步使用 call_tool/session。

## 安装与启动

项目 Python 3.11.6，使用官方 `mcp` SDK v1 维护分支（requirements-mcp.txt 固定为实际验证的 1.30.0）。不需要独立 fastmcp 包、CLI 扩展、外部数据库或新解释器。

在项目根目录 PowerShell：

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-mcp.txt
& .\.venv\Scripts\python.exe -m src.mcp_integration.server
```

服务器等待 stdin 的 MCP 协议消息；不是交互式 SQL 终端。客户端自动启动服务器，无须手动保持另一个服务进程。stdio 不监听网络端口，stdout 专用于协议。没有修改全局 MCP 配置。

## 工具与 Schema

| name | description | input schema |
|---|---|---|
| inspect_data | 检查项目 data/*.csv，返回完整 profiling | `{"type":"object","properties":{}}` |
| run_sql | 执行项目 SQLite 只读查询 | `{"type":"object","properties":{"query":{"type":"string"}},"required":["query"]}` |

SDK 根据类型注解生成 Schema（可能包含 title）。两个输出 Schema 均为 object，structuredContent 原样承载原工具 dict，不二次包装。inspect_data 返回 status/data_dir/tables/errors；SQL 返回 status/columns/rows/row_count/truncated，错误附加 error。客户端仍须检查业务 status；业务 error 与协议 isError 分开。

没有暴露任意数据库路径、导入数据库或写文件工具。inspect_data 固定默认 data 目录。读取注解只是提示；真正安全边界仍是原 run_sql：入口 SELECT/WITH、只读连接、query_only、SQLite authorizer、单语句、1000 行上限、5 秒执行超时。MCP 不绕过这些校验，也不能替 Agent 保证分析 JOIN 粒度正确。

## 离线演示和测试

```powershell
& .\.venv\Scripts\python.exe -X utf8 -m scripts.demo_mcp
& .\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -v
```

Demo 打印发现的工具 Schema，再通过 MockPlanner 和 MCP Registry 运行订单数查询。测试实际走本地 stdio，包括 profiling 与直接调用的一致性、查询/空结果/错误一致性、写操作拒绝、非法参数和未知工具。需要项目现有 Olist CSV 和 SQLite。未安装 SDK 时 6 项 MCP 测试显式 skipped，不能当作 MCP 已验证。

不读取 .env，不调用 OpenRouter，不在服务子进程环境中显式传递 API Key，不包含业务 Ground Truth。

官方参考：https://github.com/modelcontextprotocol/python-sdk/tree/v1.x
