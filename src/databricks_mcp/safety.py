"""SQL guard: validate that a query is read-only and rewrite it with a row cap.

All validation is AST-based via sqlglot — never string matching alone.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

# Catalogs/schemas an agent must not introspect through run_sql (use list_tables instead).
_BLOCKED_SCHEMAS = {
    "information_schema",
    "pg_catalog",
    "sqlite_master",
    "system",
    "sys",
}

# Table/scalar functions that read the local filesystem or attach external sources.
# These parse as ordinary read-only SELECTs but would let an agent exfiltrate local
# files (e.g. SELECT * FROM read_text('/etc/passwd')) — so they are denied outright.
_BLOCKED_FUNCTIONS = {
    "read_csv",
    "read_csv_auto",
    "read_parquet",
    "read_json",
    "read_json_auto",
    "read_ndjson",
    "read_text",
    "read_blob",
    "glob",
    "parquet_scan",
    "csv_scan",
    "delta_scan",
    "iceberg_scan",
    "sniff_csv",
}


class SQLValidationError(Exception):
    """Raised when a query is not a safe, read-only single statement."""


def _is_read_only(expr: exp.Expression) -> bool:
    # Top-level CTE queries parse as Select/Union carrying a `with` arg.
    return isinstance(expr, (exp.Select, exp.Union))


def _check_blocked_schemas(expr: exp.Expression) -> None:
    for table in expr.find_all(exp.Table):
        db = (table.text("db") or "").lower()
        name = (table.name or "").lower()
        if db in _BLOCKED_SCHEMAS or name in _BLOCKED_SCHEMAS:
            raise SQLValidationError(
                f"Access to system/catalog table '{table.sql()}' is not allowed."
            )


def _check_blocked_functions(expr: exp.Expression) -> None:
    # Unknown/file-reading functions parse as exp.Anonymous; known ones as named nodes.
    for func in expr.find_all(exp.Func):
        name = (func.sql_name() or "").lower()
        if isinstance(func, exp.Anonymous):
            name = (func.name or "").lower()
        if name in _BLOCKED_FUNCTIONS:
            raise SQLValidationError(
                f"Function '{name}' is not allowed (filesystem/external access is blocked)."
            )


def validate_and_rewrite(sql: str, max_rows: int, dialect: str = "duckdb") -> str:
    """Return a safe, row-capped SQL string or raise SQLValidationError."""
    raw = sql.strip().rstrip(";").strip()
    if not raw:
        raise SQLValidationError("Empty query.")

    try:
        statements = [s for s in sqlglot.parse(raw, read=dialect) if s is not None]
    except sqlglot.errors.ParseError as e:
        raise SQLValidationError(f"Could not parse SQL: {e}") from e

    if len(statements) != 1:
        raise SQLValidationError("Exactly one SQL statement is allowed.")

    expr = statements[0]
    if not _is_read_only(expr):
        raise SQLValidationError("Only read-only SELECT queries are allowed.")

    _check_blocked_schemas(expr)
    _check_blocked_functions(expr)

    if expr.args.get("limit") is None:
        expr = expr.limit(max_rows)

    return expr.sql(dialect=dialect)
