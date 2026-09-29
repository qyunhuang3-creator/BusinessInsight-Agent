"""Expose existing tools over MCP stdio without duplicating business logic."""

from typing import Any
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from src.tools import data_profiler, sql_tool

mcp = FastMCP("BusinessInsight", log_level="ERROR")
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)


@mcp.tool(annotations=READ_ONLY)
def inspect_data() -> dict[str, Any]:
    """Profile project data/*.csv: columns, counts, missing values, keys and <=3 sample rows.

    Returns the original structured profiling result. No path parameter is exposed.
    """
    return data_profiler.inspect_data()


@mcp.tool(annotations=READ_ONLY)
def run_sql(query: str) -> dict[str, Any]:
    """Query project Olist SQLite using one read-only SELECT or WITH...SELECT.

    Returns status, columns, rows, row_count, truncated, and error on failure.
    Existing SQL validation, authorizer, row cap and timeout remain authoritative.
    """
    return sql_tool.run_sql(query)


if __name__ == "__main__":
    mcp.run(transport="stdio")
