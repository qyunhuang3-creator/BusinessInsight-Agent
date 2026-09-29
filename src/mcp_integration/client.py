"""Small stdio client and synchronous adapter for the existing Tool Registry."""

import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parents[2]


@asynccontextmanager
async def session():
    # Do not pass os.environ or read .env. SDK inherits only its safe stdio defaults.
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "src.mcp_integration.server"],
        cwd=str(ROOT), env={"PYTHONUTF8": "1"},
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=120)) as client:
            await client.initialize()
            yield client


async def call_tool(name, arguments):
    async with session() as client:
        result = await client.call_tool(name, arguments)
        if result.isError:
            return {"status": "error", "error": {"code": "mcp_tool_error",
                    "message": "MCP rejected the tool call"}}
        if not isinstance(result.structuredContent, dict):
            raise ValueError("MCP tool did not return structuredContent")
        return result.structuredContent


def inspect_data():
    return asyncio.run(call_tool("inspect_data", {}))


def run_sql(query: str):
    return asyncio.run(call_tool("run_sql", {"query": query}))


def tool_registry():
    """Opt-in adapter for the synchronous Agent; one subprocess per invocation."""
    return {"inspect_data": inspect_data, "run_sql": run_sql}
