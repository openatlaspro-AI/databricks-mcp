"""FastMCP server exposing five read-only analytics tools."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from databricks_mcp import tools
from databricks_mcp.backends import make_backend
from databricks_mcp.config import load_settings

_settings = load_settings()
_backend = make_backend(_settings)

mcp = FastMCP("databricks-mcp")


@mcp.tool()
def list_tables() -> list[dict]:
    """List the tables available in the warehouse with their column counts."""
    return [t.model_dump() for t in tools.tool_list_tables(_backend)]


@mcp.tool()
def describe_table(table: str) -> dict:
    """Return columns, types, and row count for a table."""
    return tools.tool_describe_table(_backend, table).model_dump()


@mcp.tool()
def sample_rows(table: str, n: int = 10) -> dict:
    """Return up to `n` (max 100) preview rows from a table."""
    return tools.tool_sample_rows(_backend, table, n).model_dump()


@mcp.tool()
def run_sql(query: str) -> dict:
    """Run a read-only SELECT query. DDL/DML/multi-statement queries are rejected;
    a row LIMIT is enforced automatically."""
    return tools.tool_run_sql(_backend, query, _settings.max_rows).model_dump()


@mcp.tool()
def profile_table(table: str) -> list[dict]:
    """Return per-column null fraction, distinct count, and min/max for a table."""
    return [p.model_dump() for p in tools.tool_profile_table(_backend, table)]


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
