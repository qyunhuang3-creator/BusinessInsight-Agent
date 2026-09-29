"""Offline protocol discovery + existing MockPlanner through MCP. No LLM imports."""
import asyncio
import json
from src.agent import BusinessInsightAgent
from src.planner import MockPlanner
from src.mcp_integration.client import session, tool_registry


async def discover():
    async with session() as client:
        result = await client.list_tools()
        return [tool.model_dump(exclude_none=True) for tool in result.tools]


if __name__ == "__main__":
    print(json.dumps({"tools": asyncio.run(discover())}, ensure_ascii=False, indent=2))
    result = BusinessInsightAgent(MockPlanner(), tool_registry=tool_registry()).run(MockPlanner.DEMO_QUERY)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] == "finished" else 1)
