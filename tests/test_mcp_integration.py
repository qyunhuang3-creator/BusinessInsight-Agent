"""Real local stdio protocol tests; never call a model or external service."""
import importlib.util
import unittest

HAS_MCP = importlib.util.find_spec("mcp") is not None
if HAS_MCP:
    from src.mcp_integration.client import session, tool_registry
    from src.tools.data_profiler import inspect_data
    from src.tools.sql_tool import run_sql
    from src.agent import BusinessInsightAgent
    from src.planner import MockPlanner


@unittest.skipUnless(HAS_MCP, "Install requirements-mcp.txt to run real MCP tests")
class MCPProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def test_discovery_and_schemas(self):
        async with session() as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            self.assertEqual(set(tools), {"inspect_data", "run_sql"})
            self.assertEqual(tools["inspect_data"].inputSchema.get("properties"), {})
            self.assertEqual(tools["run_sql"].inputSchema["required"], ["query"])
            self.assertEqual(tools["run_sql"].inputSchema["properties"]["query"]["type"], "string")
            for tool in tools.values():
                self.assertTrue(tool.description)
                self.assertEqual(tool.outputSchema["type"], "object")
                self.assertTrue(tool.annotations.readOnlyHint)

    async def test_sql_matches_existing_tool(self):
        async with session() as client:
            for query in ["SELECT COUNT(*) AS order_count FROM orders", "SELECT 1 WHERE 0", "SELECT * FROM absent_test_table"]:
                result = await client.call_tool("run_sql", {"query": query})
                self.assertFalse(result.isError)
                self.assertEqual(result.structuredContent, run_sql(query))

    async def test_inspection_matches_existing_tool(self):
        async with session() as client:
            result = await client.call_tool("inspect_data", {})
            self.assertFalse(result.isError)
            self.assertEqual(result.structuredContent, inspect_data())

    async def test_writes_rejected(self):
        async with session() as client:
            for query in ["DELETE FROM orders", "DROP TABLE orders", "WITH x AS (SELECT 1) DELETE FROM orders", "SELECT 1; DELETE FROM orders"]:
                result = await client.call_tool("run_sql", {"query": query})
                self.assertEqual(result.structuredContent, run_sql(query))
                self.assertEqual(result.structuredContent["status"], "error")

    async def test_invalid_input_and_unknown_tool(self):
        async with session() as client:
            for name, arguments in [("run_sql", {}), ("run_sql", {"query": []}), ("unknown", {})]:
                self.assertTrue((await client.call_tool(name, arguments)).isError)


@unittest.skipUnless(HAS_MCP, "Install requirements-mcp.txt to run real MCP tests")
class MCPAgentTests(unittest.TestCase):
    def test_existing_agent_with_mcp_registry(self):
        result = BusinessInsightAgent(MockPlanner(), tool_registry=tool_registry()).run(MockPlanner.DEMO_QUERY)
        expected = run_sql("SELECT COUNT(*) FROM orders")["rows"][0][0]
        self.assertEqual(result["status"], "finished")
        self.assertIn(f"{expected:,}", result["answer"])
