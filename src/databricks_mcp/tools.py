"""Tool orchestration — pure functions over a Backend. No MCP transport here,
so these are directly unit-testable."""

from __future__ import annotations

from databricks_mcp.backends.base import Backend
from databricks_mcp.models import ColumnProfile, QueryResult, TableInfo, TableSchema
from databricks_mcp.safety import validate_and_rewrite


def tool_list_tables(backend: Backend) -> list[TableInfo]:
    return backend.list_tables()


def tool_describe_table(backend: Backend, table: str) -> TableSchema:
    return backend.describe_table(table)


def tool_sample_rows(backend: Backend, table: str, n: int = 10) -> QueryResult:
    return backend.sample_rows(table, n)


def tool_run_sql(backend: Backend, query: str, max_rows: int) -> QueryResult:
    safe_sql = validate_and_rewrite(query, max_rows=max_rows, dialect=backend.dialect)
    return backend.run_query(safe_sql, max_rows)


def tool_profile_table(backend: Backend, table: str) -> list[ColumnProfile]:
    return backend.profile_table(table)
