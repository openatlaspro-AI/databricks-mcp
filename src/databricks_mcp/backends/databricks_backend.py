"""Databricks SQL Warehouse backend. Activated by DB_BACKEND=databricks.

Schema introspection uses the warehouse's information_schema; user queries from
run_query are pre-validated by safety.validate_and_rewrite before they arrive here.
"""

from __future__ import annotations

from databricks import sql

from databricks_mcp.backends.base import ensure_known_table
from databricks_mcp.models import ColumnInfo, ColumnProfile, QueryResult, TableInfo, TableSchema


class DatabricksBackend:
    dialect = "databricks"

    def __init__(self, hostname: str | None, http_path: str | None, token: str | None):
        if not (hostname and http_path and token):
            raise ValueError(
                "Databricks backend requires DATABRICKS_SERVER_HOSTNAME, "
                "DATABRICKS_HTTP_PATH, and DATABRICKS_TOKEN."
            )
        self._conn = sql.connect(
            server_hostname=hostname, http_path=http_path, access_token=token
        )

    def _query(self, statement: str, max_rows: int) -> QueryResult:
        cur = self._conn.cursor()
        try:
            cur.execute(statement)
            columns = [d[0] for d in cur.description]
            rows = cur.fetchmany(max_rows)
            truncated = cur.fetchone() is not None
            return QueryResult(
                columns=columns,
                rows=[list(r) for r in rows],
                row_count=len(rows),
                truncated=truncated,
            )
        finally:
            cur.close()

    def _known(self) -> list[str]:
        res = self._query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema()",
            10000,
        )
        return [r[0] for r in res.rows]

    def list_tables(self) -> list[TableInfo]:
        out = []
        for name in self._known():
            schema = self.describe_table(name)
            out.append(TableInfo(name=name, column_count=len(schema.columns)))
        return out

    def describe_table(self, table: str) -> TableSchema:
        ensure_known_table(table, self._known())
        cols = self._query(
            "SELECT column_name, data_type FROM information_schema.columns "
            f"WHERE table_name = '{table}' AND table_schema = current_schema()",
            10000,
        )
        n = self._query(f"SELECT count(*) FROM {table}", 1)
        return TableSchema(
            table=table,
            columns=[ColumnInfo(name=r[0], type=r[1]) for r in cols.rows],
            row_count=int(n.rows[0][0]),
        )

    def sample_rows(self, table: str, n: int) -> QueryResult:
        ensure_known_table(table, self._known())
        n = max(1, min(int(n), 100))
        return self._query(f"SELECT * FROM {table} LIMIT {n}", n)

    def run_query(self, safe_sql: str, max_rows: int) -> QueryResult:
        return self._query(safe_sql, max_rows)

    def profile_table(self, table: str) -> list[ColumnProfile]:
        ensure_known_table(table, self._known())
        schema = self.describe_table(table)
        total = max(schema.row_count, 1)
        profiles = []
        for col in schema.columns:
            name = col.name
            res = self._query(
                f"SELECT count_if({name} IS NULL), count(DISTINCT {name}), "
                f"min({name}), max({name}) FROM {table}",
                1,
            )
            nulls, distinct, lo, hi = res.rows[0]
            profiles.append(
                ColumnProfile(
                    column=name,
                    null_fraction=round(nulls / total, 4),
                    distinct_count=int(distinct),
                    min=None if lo is None else str(lo),
                    max=None if hi is None else str(hi),
                )
            )
        return profiles
