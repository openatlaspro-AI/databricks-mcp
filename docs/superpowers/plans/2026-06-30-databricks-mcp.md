# databricks-mcp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and publish an open-source MCP server giving AI agents safe, read-only SQL analytics over a local DuckDB sample warehouse (default) and a real Databricks SQL Warehouse (via env).

**Architecture:** A thin FastMCP server (`server.py`) wires five tools to a pluggable `Backend` (DuckDB or Databricks). Every query passes through `safety.py` (sqlglot AST validation: single-statement, SELECT-only, system-table block, auto-LIMIT). Tool orchestration lives in `tools.py` so it is testable without the MCP transport.

**Tech Stack:** Python 3.11+, MCP Python SDK (FastMCP), DuckDB, databricks-sql-connector, sqlglot, pydantic, pytest, ruff, GitHub Actions.

---

## File Structure

```
databricks-mcp/
  pyproject.toml                      # package + deps + entry point + ruff/pytest config
  README.md                           # quickstart, Claude config, guardrails, transcript
  LICENSE                             # MIT
  .github/workflows/ci.yml            # pytest on push
  src/databricks_mcp/
    __init__.py
    config.py                         # env-driven settings (backend choice, MAX_ROWS, creds)
    safety.py                         # sqlglot guard: validate_and_rewrite()
    models.py                         # pydantic response models
    tools.py                          # orchestration: tool_* functions taking a Backend
    server.py                         # FastMCP server + main() entry point
    backends/
      __init__.py                     # make_backend() factory
      base.py                         # Backend Protocol + shared identifier guard
      duckdb_backend.py               # default; views over bundled parquet
      databricks_backend.py           # databricks-sql-connector
  sample_data/
    generate.py                       # deterministic synthetic logistics data -> parquet
    shipments.parquet                 # committed (generated)
    carriers.parquet                  # committed (generated)
    lanes.parquet                     # committed (generated)
  tests/
    conftest.py                       # duckdb backend fixture
    test_safety.py
    test_duckdb_backend.py
    test_tools.py
    test_databricks_backend.py
    test_server_smoke.py
```

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/databricks_mcp/__init__.py`
- Create: `src/databricks_mcp/config.py`
- Create: `tests/conftest.py` (placeholder, filled in Task 4)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "databricks-mcp"
version = "0.1.0"
description = "Safe, read-only SQL analytics MCP server for AI agents — local DuckDB default + Databricks SQL Warehouse"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Mark Teji" }]
keywords = ["mcp", "databricks", "duckdb", "sql", "ai-agents", "model-context-protocol"]
dependencies = [
  "mcp>=1.2.0",
  "duckdb>=1.1.0",
  "sqlglot>=25.0.0",
  "pydantic>=2.6.0",
  "databricks-sql-connector>=3.4.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6.0"]

[project.scripts]
databricks-mcp = "databricks_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/databricks_mcp"]

[tool.hatch.build.targets.wheel.force-include]
"sample_data" = "databricks_mcp/sample_data"

[tool.pytest.ini_options]
addopts = "-v --tb=short"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"
```

- [ ] **Step 2: Write `src/databricks_mcp/__init__.py`**

```python
"""databricks-mcp: safe read-only SQL analytics over MCP."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write `src/databricks_mcp/config.py`**

```python
"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    backend: str  # "duckdb" | "databricks"
    max_rows: int
    # Databricks (only required when backend == "databricks")
    databricks_hostname: str | None
    databricks_http_path: str | None
    databricks_token: str | None


def load_settings() -> Settings:
    return Settings(
        backend=os.getenv("DB_BACKEND", "duckdb").strip().lower(),
        max_rows=int(os.getenv("MAX_ROWS", "1000")),
        databricks_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        databricks_http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        databricks_token=os.getenv("DATABRICKS_TOKEN"),
    )
```

- [ ] **Step 4: Create empty `tests/conftest.py`**

```python
# Fixtures added in Task 4.
```

- [ ] **Step 5: Create the virtualenv and install**

Run:
```bash
cd ~/projects/databricks-mcp
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
```
Expected: installs without error; `databricks-mcp` console script is created.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/databricks_mcp/__init__.py src/databricks_mcp/config.py tests/conftest.py
git commit -m "chore: scaffold databricks-mcp package"
```

---

### Task 2: Synthetic logistics sample data

**Files:**
- Create: `sample_data/generate.py`
- Create (generated, committed): `sample_data/shipments.parquet`, `carriers.parquet`, `lanes.parquet`

- [ ] **Step 1: Write `sample_data/generate.py`**

```python
"""Generate deterministic synthetic logistics/freight data as parquet.

Tables:
  carriers(carrier_id, carrier_name, mode, on_time_rate)
  lanes(lane_id, origin, destination, miles)
  shipments(shipment_id, carrier_id, lane_id, ship_date, weight_lbs, cost_usd, delivered_on_time)
"""

from __future__ import annotations

import os

import duckdb

HERE = os.path.dirname(__file__)


def main() -> None:
    con = duckdb.connect()
    con.execute("SELECT setseed(0.42)")

    con.execute(
        """
        CREATE TABLE carriers AS
        SELECT
            i AS carrier_id,
            'Carrier_' || i AS carrier_name,
            ['LTL', 'FTL', 'Parcel', 'Intermodal'][1 + (i % 4)] AS mode,
            round(0.80 + (i % 20) / 100.0, 3) AS on_time_rate
        FROM range(1, 13) t(i)
        """
    )
    con.execute(
        """
        CREATE TABLE lanes AS
        SELECT
            i AS lane_id,
            ['Toronto', 'Chicago', 'Dallas', 'Newark', 'Atlanta', 'Denver'][1 + (i % 6)] AS origin,
            ['Montreal', 'Detroit', 'Houston', 'Boston', 'Miami', 'Phoenix'][1 + (i % 6)] AS destination,
            200 + (i * 37) % 2200 AS miles
        FROM range(1, 25) t(i)
        """
    )
    con.execute(
        """
        CREATE TABLE shipments AS
        SELECT
            i AS shipment_id,
            1 + (i % 12) AS carrier_id,
            1 + (i % 24) AS lane_id,
            DATE '2026-01-01' + ((i * 7) % 180) AS ship_date,
            500 + (i * 113) % 19500 AS weight_lbs,
            round(150 + ((i * 91) % 4800) / 1.0, 2) AS cost_usd,
            ((i * 17) % 100) < 88 AS delivered_on_time
        FROM range(1, 5001) t(i)
        """
    )

    for table in ("carriers", "lanes", "shipments"):
        out = os.path.join(HERE, f"{table}.parquet")
        con.execute(f"COPY {table} TO '{out}' (FORMAT parquet)")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the parquet files**

Run:
```bash
cd ~/projects/databricks-mcp && python sample_data/generate.py
```
Expected: prints three `wrote .../*.parquet` lines; files exist.

- [ ] **Step 3: Verify the data loads**

Run:
```bash
python -c "import duckdb; print(duckdb.sql(\"SELECT count(*) FROM read_parquet('sample_data/shipments.parquet')\").fetchone())"
```
Expected: `(5000,)`

- [ ] **Step 4: Commit**

```bash
git add sample_data/
git commit -m "feat: add deterministic synthetic logistics sample data"
```

---

### Task 3: Safety module (sqlglot guard)

**Files:**
- Create: `src/databricks_mcp/safety.py`
- Test: `tests/test_safety.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_safety.py
import pytest

from databricks_mcp.safety import SQLValidationError, validate_and_rewrite


def test_plain_select_gets_auto_limit():
    out = validate_and_rewrite("SELECT * FROM shipments", max_rows=1000)
    assert "LIMIT 1000" in out.upper()


def test_existing_limit_is_preserved():
    out = validate_and_rewrite("SELECT * FROM shipments LIMIT 5", max_rows=1000)
    assert out.upper().count("LIMIT") == 1
    assert "LIMIT 5" in out.upper()


def test_cte_select_is_allowed():
    out = validate_and_rewrite(
        "WITH x AS (SELECT 1 AS a) SELECT a FROM x", max_rows=10
    )
    assert "LIMIT 10" in out.upper()


@pytest.mark.parametrize(
    "sql",
    [
        "DROP TABLE shipments",
        "DELETE FROM shipments",
        "UPDATE shipments SET cost_usd = 0",
        "INSERT INTO shipments VALUES (1)",
        "CREATE TABLE x (a INT)",
        "ALTER TABLE shipments ADD COLUMN x INT",
        "ATTACH 'x.db' AS y",
        "PRAGMA database_list",
    ],
)
def test_non_read_only_is_rejected(sql):
    with pytest.raises(SQLValidationError):
        validate_and_rewrite(sql, max_rows=1000)


def test_multi_statement_is_rejected():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT 1; DROP TABLE shipments", max_rows=1000)


def test_unparseable_is_rejected():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELEKT bogus", max_rows=1000)


def test_system_table_is_blocked():
    with pytest.raises(SQLValidationError):
        validate_and_rewrite("SELECT * FROM information_schema.tables", max_rows=1000)


def test_trailing_semicolon_is_fine():
    out = validate_and_rewrite("SELECT 1 AS a;", max_rows=10)
    assert "LIMIT 10" in out.upper()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_safety.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'databricks_mcp.safety'`

- [ ] **Step 3: Write `src/databricks_mcp/safety.py`**

```python
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

    if expr.args.get("limit") is None:
        expr = expr.limit(max_rows)

    return expr.sql(dialect=dialect)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_safety.py -v`
Expected: PASS (all cases). If `PRAGMA`/`ATTACH` parse to a non-Select expression, `_is_read_only` returns False and they are rejected as required.

- [ ] **Step 5: Commit**

```bash
git add src/databricks_mcp/safety.py tests/test_safety.py
git commit -m "feat: add sqlglot read-only SQL guard with auto-LIMIT"
```

---

### Task 4: Backend protocol + DuckDB backend

**Files:**
- Create: `src/databricks_mcp/models.py`
- Create: `src/databricks_mcp/backends/__init__.py`
- Create: `src/databricks_mcp/backends/base.py`
- Create: `src/databricks_mcp/backends/duckdb_backend.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_duckdb_backend.py`

- [ ] **Step 1: Write `src/databricks_mcp/models.py`**

```python
"""Pydantic response models — these define the agent-facing tool schemas."""

from __future__ import annotations

from pydantic import BaseModel


class TableInfo(BaseModel):
    name: str
    column_count: int


class ColumnInfo(BaseModel):
    name: str
    type: str


class TableSchema(BaseModel):
    table: str
    columns: list[ColumnInfo]
    row_count: int


class QueryResult(BaseModel):
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool


class ColumnProfile(BaseModel):
    column: str
    null_fraction: float
    distinct_count: int
    min: str | None
    max: str | None
```

- [ ] **Step 2: Write `src/databricks_mcp/backends/base.py`**

```python
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
```

- [ ] **Step 3: Write `src/databricks_mcp/backends/duckdb_backend.py`**

```python
"""DuckDB backend: in-memory views over the bundled logistics parquet files."""

from __future__ import annotations

import os

import duckdb

from databricks_mcp.backends.base import ensure_known_table
from databricks_mcp.models import ColumnProfile, ColumnInfo, QueryResult, TableInfo, TableSchema

_SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_data")
_TABLES = ("carriers", "lanes", "shipments")


class DuckDBBackend:
    dialect = "duckdb"

    def __init__(self, sample_dir: str = _SAMPLE_DIR):
        self._con = duckdb.connect()
        for name in _TABLES:
            path = os.path.join(sample_dir, f"{name}.parquet")
            self._con.execute(
                f"CREATE VIEW {name} AS SELECT * FROM read_parquet(?)", [path]
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
```

- [ ] **Step 4: Write `tests/conftest.py`**

```python
import pytest

from databricks_mcp.backends.duckdb_backend import DuckDBBackend


@pytest.fixture
def backend():
    return DuckDBBackend()
```

- [ ] **Step 5: Write the failing tests**

```python
# tests/test_duckdb_backend.py
import pytest

from databricks_mcp.backends.base import UnknownTableError


def test_list_tables(backend):
    names = {t.name for t in backend.list_tables()}
    assert names == {"carriers", "lanes", "shipments"}


def test_describe_table(backend):
    schema = backend.describe_table("shipments")
    assert schema.row_count == 5000
    assert "shipment_id" in {c.name for c in schema.columns}


def test_sample_rows_caps_at_n(backend):
    res = backend.sample_rows("shipments", 5)
    assert res.row_count == 5
    assert len(res.columns) > 0


def test_run_query_truncates(backend):
    res = backend.run_query("SELECT * FROM shipments LIMIT 3", max_rows=3)
    assert res.row_count == 3
    assert res.truncated is True


def test_run_query_not_truncated_when_fewer_rows(backend):
    res = backend.run_query("SELECT * FROM carriers", max_rows=1000)
    assert res.truncated is False


def test_profile_table(backend):
    profs = {p.column: p for p in backend.profile_table("carriers")}
    assert profs["carrier_id"].distinct_count == 12
    assert profs["carrier_id"].null_fraction == 0.0


def test_unknown_table_rejected(backend):
    with pytest.raises(UnknownTableError):
        backend.describe_table("secrets")
```

- [ ] **Step 6: Run tests to verify they fail then pass**

Run: `pytest tests/test_duckdb_backend.py -v`
Expected: FAIL first (before Step 3 exists), PASS after the backend is implemented.

- [ ] **Step 7: Commit**

```bash
git add src/databricks_mcp/models.py src/databricks_mcp/backends/ tests/conftest.py tests/test_duckdb_backend.py
git commit -m "feat: add Backend protocol and DuckDB backend"
```

---

### Task 5: Tool orchestration layer

**Files:**
- Create: `src/databricks_mcp/tools.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tools.py
import pytest

from databricks_mcp import tools
from databricks_mcp.safety import SQLValidationError


def test_tool_run_sql_happy(backend):
    res = tools.tool_run_sql(backend, "SELECT carrier_id FROM carriers", max_rows=1000)
    assert res.row_count == 12
    assert res.columns == ["carrier_id"]


def test_tool_run_sql_blocks_ddl(backend):
    with pytest.raises(SQLValidationError):
        tools.tool_run_sql(backend, "DROP TABLE carriers", max_rows=1000)


def test_tool_list_tables(backend):
    res = tools.tool_list_tables(backend)
    assert {t.name for t in res} == {"carriers", "lanes", "shipments"}


def test_tool_describe(backend):
    res = tools.tool_describe_table(backend, "lanes")
    assert res.table == "lanes"


def test_tool_profile(backend):
    res = tools.tool_profile_table(backend, "carriers")
    assert any(p.column == "on_time_rate" for p in res)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_tools.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'databricks_mcp.tools'`

- [ ] **Step 3: Write `src/databricks_mcp/tools.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tools.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/databricks_mcp/tools.py tests/test_tools.py
git commit -m "feat: add tool orchestration layer with guarded run_sql"
```

---

### Task 6: FastMCP server + backend factory + entry point

**Files:**
- Modify: `src/databricks_mcp/backends/__init__.py`
- Create: `src/databricks_mcp/server.py`
- Test: `tests/test_server_smoke.py`

- [ ] **Step 1: Write `src/databricks_mcp/backends/__init__.py`**

```python
"""Backend factory selected by Settings."""

from __future__ import annotations

from databricks_mcp.backends.base import Backend
from databricks_mcp.config import Settings


def make_backend(settings: Settings) -> Backend:
    if settings.backend == "databricks":
        from databricks_mcp.backends.databricks_backend import DatabricksBackend

        return DatabricksBackend(
            hostname=settings.databricks_hostname,
            http_path=settings.databricks_http_path,
            token=settings.databricks_token,
        )
    from databricks_mcp.backends.duckdb_backend import DuckDBBackend

    return DuckDBBackend()
```

- [ ] **Step 2: Write `src/databricks_mcp/server.py`**

```python
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
```

- [ ] **Step 3: Write the smoke test**

```python
# tests/test_server_smoke.py
def test_server_registers_five_tools():
    from databricks_mcp import server

    # FastMCP exposes registered tools; assert our five are present.
    import asyncio

    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert {"list_tables", "describe_table", "sample_rows", "run_sql", "profile_table"} <= names


def test_run_sql_tool_callable_end_to_end():
    from databricks_mcp import server

    result = server.run_sql("SELECT count(*) AS n FROM shipments")
    assert result["columns"] == ["n"]
    assert result["rows"][0][0] == 5000
```

- [ ] **Step 4: Run the smoke test**

Run: `pytest tests/test_server_smoke.py -v`
Expected: PASS. (If `list_tools()` is not async in the installed SDK version, replace `asyncio.run(server.mcp.list_tools())` with `server.mcp.list_tools()` — adjust to the actual return type, keeping the name assertion.)

- [ ] **Step 5: Manual MCP run check**

Run:
```bash
DB_BACKEND=duckdb timeout 3 databricks-mcp || true
```
Expected: process starts and waits on stdio (no crash, no traceback) before timeout kills it.

- [ ] **Step 6: Commit**

```bash
git add src/databricks_mcp/server.py src/databricks_mcp/backends/__init__.py tests/test_server_smoke.py
git commit -m "feat: add FastMCP server, backend factory, and entry point"
```

---

### Task 7: Databricks backend (mock-tested)

**Files:**
- Create: `src/databricks_mcp/backends/databricks_backend.py`
- Test: `tests/test_databricks_backend.py`

- [ ] **Step 1: Write the failing tests (driver mocked — no live warehouse in CI)**

```python
# tests/test_databricks_backend.py
from unittest.mock import MagicMock, patch

import pytest

from databricks_mcp.backends.databricks_backend import DatabricksBackend


def _fake_cursor(rows, description):
    cur = MagicMock()
    cur.description = description
    cur.fetchmany.return_value = rows[:]
    cur.fetchone.return_value = None
    return cur


@patch("databricks_mcp.backends.databricks_backend.sql")
def test_run_query_maps_rows(mock_sql):
    cur = _fake_cursor([[5000]], [("n",)])
    conn = MagicMock()
    conn.cursor.return_value = cur
    mock_sql.connect.return_value = conn

    be = DatabricksBackend(hostname="h", http_path="p", token="t")
    res = be.run_query("SELECT count(*) AS n FROM shipments LIMIT 1000", max_rows=1000)

    assert res.columns == ["n"]
    assert res.rows == [[5000]]
    assert res.truncated is False


def test_missing_credentials_raises():
    with pytest.raises(ValueError):
        DatabricksBackend(hostname=None, http_path=None, token=None)
```

- [ ] **Step 2: Run to verify failure**

Run: `pytest tests/test_databricks_backend.py -v`
Expected: FAIL with `ModuleNotFoundError` for `databricks_backend`.

- [ ] **Step 3: Write `src/databricks_mcp/backends/databricks_backend.py`**

```python
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
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_databricks_backend.py -v`
Expected: PASS (driver mocked).

- [ ] **Step 5: Commit**

```bash
git add src/databricks_mcp/backends/databricks_backend.py tests/test_databricks_backend.py
git commit -m "feat: add Databricks SQL Warehouse backend"
```

---

### Task 8: README, LICENSE, CI

**Files:**
- Create: `LICENSE`
- Create: `README.md`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `LICENSE`** (standard MIT text, author "Mark Teji", year 2026).

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

```yaml
name: CI
on:
  push:
  pull_request:
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"
      - name: Lint
        run: ruff check .
      - name: Test
        run: pytest
```

- [ ] **Step 3: Write `README.md`**

Sections (write each in full):
- **Title + one-line pitch** + badges (CI, license, Python).
- **What it is:** read-only SQL analytics over MCP; DuckDB default, Databricks via env. Explicit note that the name reflects the Databricks backend; it also runs fully offline on DuckDB.
- **30-second quickstart:**
  ```bash
  uvx databricks-mcp           # runs on bundled DuckDB logistics sample data
  ```
- **Claude Desktop config** snippet:
  ```json
  {
    "mcpServers": {
      "databricks-mcp": { "command": "uvx", "args": ["databricks-mcp"] }
    }
  }
  ```
- **Connecting real Databricks:**
  ```bash
  export DB_BACKEND=databricks
  export DATABRICKS_SERVER_HOSTNAME=...
  export DATABRICKS_HTTP_PATH=...
  export DATABRICKS_TOKEN=...
  ```
- **Tools table** (the five tools + descriptions).
- **Safety / guardrails:** bullet the five rules from `safety.py`, and link the tests as proof.
- **Recorded transcript:** a fenced example of an agent calling `list_tables` → `run_sql` and getting freight analytics back.
- **Development:** `uv venv && uv pip install -e ".[dev]" && pytest`.

- [ ] **Step 4: Verify everything passes together**

Run: `cd ~/projects/databricks-mcp && ruff check . && pytest`
Expected: ruff clean; all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md LICENSE .github/workflows/ci.yml
git commit -m "docs: add README, MIT license, and CI workflow"
```

- [ ] **Step 6: Publish to GitHub**

Run:
```bash
gh repo create openatlaspro-AI/databricks-mcp --public --source=. --remote=origin --push \
  --description "Safe, read-only SQL analytics MCP server for AI agents — DuckDB default + Databricks SQL Warehouse, with sqlglot guardrails."
```
Expected: repo created and pushed; CI runs green on GitHub.

---

## Self-Review

**Spec coverage:**
- Purpose / dual backend → Tasks 4, 6, 7. ✓
- 5 tools → Task 5 (orchestration) + Task 6 (MCP surface). ✓
- Safety model (parse, single-statement, read-only allowlist, system-table block, auto-LIMIT, structured errors) → Task 3, all six rules covered with tests. ✓ (EXPLAIN dropped from v1 — non-Select statements are uniformly rejected, which is safer; spec's "EXPLAIN" allowance is the one deliberate trim. Update spec note at build time.)
- Sample logistics data → Task 2. ✓
- Tests + guardrail proof → Tasks 3–7. ✓
- README + Claude config + transcript → Task 8. ✓
- MIT, uvx, CI → Tasks 1, 8. ✓
- Resume bullet → earned once Task 8 publishes. ✓

**Placeholder scan:** README sub-bullets in Task 8 Step 3 are described rather than shown verbatim; every code/SQL/test step elsewhere is complete. Acceptable — README prose is the one place full text is composed at write time from the listed sections.

**Type consistency:** `Backend` protocol methods (`list_tables`, `describe_table`, `sample_rows`, `run_query(safe_sql, max_rows)`, `profile_table`) match both backends and the `tools.tool_*` callers and the `server` MCP wrappers. Model names (`TableInfo`, `ColumnInfo`, `TableSchema`, `QueryResult`, `ColumnProfile`) are consistent across models.py, backends, tools, and tests.

**Deviation noted:** v1 drops the EXPLAIN allowance to keep the read-only check provably correct (Select/Union only). This is a tightening, not a gap.
