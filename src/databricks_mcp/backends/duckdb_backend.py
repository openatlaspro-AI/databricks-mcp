"""DuckDB backend: in-memory views over the bundled logistics parquet files."""

from __future__ import annotations

import os

import duckdb

from databricks_mcp.backends.base import ensure_known_table
from databricks_mcp.models import ColumnProfile, ColumnInfo, QueryResult, TableInfo, TableSchema

def _default_sample_dir() -> str:
    # Packaged location (wheel force-includes sample_data into the package).
    packaged = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")
    if os.path.isdir(packaged):
        return packaged
    # Editable/source checkout: parquet lives at the repo root's sample_data/.
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    return os.path.join(repo_root, "sample_data")


_SAMPLE_DIR = _default_sample_dir()
_TABLES = ("carriers", "lanes", "shipments")


class DuckDBBackend:
    dialect = "duckdb"

    def __init__(self, sample_dir: str = _SAMPLE_DIR):
        self._con = duckdb.connect()
        for name in _TABLES:
            path = os.path.join(sample_dir, f"{name}.parquet")
            literal = path.replace("'", "''")
            self._con.execute(
                f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{literal}')"
            )

    def _known(self) -> list[str]:
        return list(_TABLES)

    def list_tables(self) -> list[TableInfo]:
        out = []
        for name in _TABLES:
            cols = self._con.execute(f"DESCRIBE {name}").fetchall()
            out.append(TableInfo(name=name, column_count=len(cols)))
        return out

    def describe_table(self, table: str) -> TableSchema:
        ensure_known_table(table, self._known())
        cols = self._con.execute(f"DESCRIBE {table}").fetchall()
        n = self._con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        return TableSchema(
            table=table,
            columns=[ColumnInfo(name=c[0], type=c[1]) for c in cols],
            row_count=int(n),
        )

    def sample_rows(self, table: str, n: int) -> QueryResult:
        ensure_known_table(table, self._known())
        n = max(1, min(int(n), 100))
        cur = self._con.execute(f"SELECT * FROM {table} LIMIT {n}")
        return self._to_result(cur, n)

    def run_query(self, safe_sql: str, max_rows: int) -> QueryResult:
        cur = self._con.execute(safe_sql)
        return self._to_result(cur, max_rows)

    def profile_table(self, table: str) -> list[ColumnProfile]:
        ensure_known_table(table, self._known())
        total = self._con.execute(f"SELECT count(*) FROM {table}").fetchone()[0] or 1
        cols = self._con.execute(f"DESCRIBE {table}").fetchall()
        profiles = []
        for c in cols:
            name = c[0]
            nulls, distinct, lo, hi = self._con.execute(
                f"SELECT count(*) FILTER (WHERE {name} IS NULL), "
                f"count(DISTINCT {name}), min({name}), max({name}) FROM {table}"
            ).fetchone()
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

    def _to_result(self, cur, max_rows: int) -> QueryResult:
        columns = [d[0] for d in cur.description]
        rows = cur.fetchmany(max_rows)
        extra = cur.fetchone()
        return QueryResult(
            columns=columns,
            rows=[list(r) for r in rows],
            row_count=len(rows),
            truncated=extra is not None,
        )
