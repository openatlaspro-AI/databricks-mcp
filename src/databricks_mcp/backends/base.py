"""Backend protocol + a shared guard for table-identifier arguments."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from databricks_mcp.models import ColumnProfile, QueryResult, TableInfo, TableSchema


class UnknownTableError(Exception):
    """Raised when a tool is given a table name that is not in the warehouse."""


@runtime_checkable
class Backend(Protocol):
    dialect: str

    def list_tables(self) -> list[TableInfo]: ...
    def describe_table(self, table: str) -> TableSchema: ...
    def sample_rows(self, table: str, n: int) -> QueryResult: ...
    def run_query(self, safe_sql: str, max_rows: int) -> QueryResult: ...
    def profile_table(self, table: str) -> list[ColumnProfile]: ...


def ensure_known_table(table: str, known: list[str]) -> str:
    """Return the table name if known, else raise. Prevents identifier injection
    in tools that interpolate a table name into SQL."""
    if table not in known:
        raise UnknownTableError(
            f"Unknown table '{table}'. Known tables: {', '.join(sorted(known))}"
        )
    return table
