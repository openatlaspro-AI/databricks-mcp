# databricks-mcp

**Safe, read-only SQL analytics for AI agents — over MCP.** Point an agent at a SQL warehouse
and let it explore, profile, and query data without any risk of mutating it.

[![CI](https://github.com/openatlaspro-AI/databricks-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/openatlaspro-AI/databricks-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

## What it is

`databricks-mcp` is a [Model Context Protocol](https://modelcontextprotocol.io) server that gives
an AI agent **safe, read-only analytics access to a SQL warehouse**. It exposes five typed tools —
`list_tables`, `describe_table`, `sample_rows`, `run_sql`, and `profile_table` — and routes every
query through an AST-based safety guard that enforces read-only, single-statement, and row-cap
guarantees.

Two backends ship in the box:

- **DuckDB (default)** — runs fully offline against a bundled synthetic logistics warehouse
  (shipments, carriers, lanes). Zero setup, ~30 seconds to first query.
- **Databricks SQL Warehouse** — connect to a real warehouse with a few environment variables.

> **About the name:** the project is named for its Databricks backend, but it runs completely
> offline on DuckDB out of the box — you don't need a Databricks account to try it.

## 30-second quickstart

```bash
uvx databricks-mcp           # runs on the bundled DuckDB logistics sample data
```

That's it — the server starts on stdio with the sample warehouse loaded and waits for an MCP
client.

## Claude Desktop config

Add this to your Claude Desktop MCP configuration (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "databricks-mcp": { "command": "uvx", "args": ["databricks-mcp"] }
  }
}
```

Restart Claude Desktop and the five tools become available to the assistant.

## Connecting a real Databricks SQL Warehouse

Set the backend to `databricks` and provide your warehouse credentials via environment variables:

```bash
export DB_BACKEND=databricks
export DATABRICKS_SERVER_HOSTNAME=...     # e.g. dbc-xxxxxxxx-xxxx.cloud.databricks.com
export DATABRICKS_HTTP_PATH=...           # e.g. /sql/1.0/warehouses/abc123
export DATABRICKS_TOKEN=...               # a Databricks personal access token
```

Optionally cap the maximum rows any single query may return (default `1000`):

```bash
export MAX_ROWS=500
```

Secrets are only ever read from the environment and are never logged.

## Tools

| Tool | Input | Output |
|---|---|---|
| `list_tables` | — | Table names and column counts. |
| `describe_table` | `table` | Columns, types, and row count. |
| `sample_rows` | `table`, `n` (default 10, max 100) | Preview rows from the table. |
| `run_sql` | `query` | Guarded read-only result rows (row-capped). |
| `profile_table` | `table` | Per-column null fraction, distinct count, and min/max. |

All inputs and outputs are typed with `pydantic` models, so the agent receives clean JSON schemas.

## Safety / guardrails

Every query passed to `run_sql` — and every statement the other tools generate internally —
goes through `safety.py`, which validates against the parsed [sqlglot](https://github.com/tobymao/sqlglot)
AST rather than fragile string matching:

1. **Parse or reject.** Anything that fails to parse is rejected with a structured error.
2. **Single statement only.** Multi-statement input is rejected, blocking stacked-query injection.
3. **Read-only only.** Only `SELECT` and CTE (`WITH`) queries are allowed. Any
   `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/GRANT/COPY/CALL/PRAGMA/ATTACH` is rejected.
4. **System-table block.** References to `information_schema`, `pg_catalog`, `system`, and similar
   catalogs are denied — agents introspect schema through `list_tables`/`describe_table` instead.
5. **Filesystem-function block.** Read-only SELECTs can still call table functions like
   `read_csv`, `read_parquet`, `read_text`, and `glob` to read local files. The guard walks the AST
   and denies these, so an agent can't exfiltrate the host filesystem (e.g.
   `SELECT * FROM read_text('/etc/passwd')`).
6. **Auto-LIMIT.** A `LIMIT` (default `1000`, configurable via `MAX_ROWS`) is injected when absent,
   so an agent can never pull unbounded data.

Identifier arguments (`table`) are additionally checked against the known-table list before they
are ever interpolated into SQL, preventing identifier injection.

Every one of these rules is backed by a passing test — see
[`tests/test_safety.py`](tests/test_safety.py) (read-only allowlist, multi-statement, unparseable,
system-table, filesystem-function, and auto-LIMIT cases) and [`tests/test_duckdb_backend.py`](tests/test_duckdb_backend.py)
(unknown-table rejection, row-cap truncation). The README makes no guardrail claim that isn't
proven by the suite.

## Recorded transcript

An agent exploring the bundled logistics warehouse:

```
> list_tables
[
  {"name": "carriers",  "column_count": 4},
  {"name": "lanes",     "column_count": 4},
  {"name": "shipments", "column_count": 7}
]

> run_sql: SELECT c.mode,
                  count(*)                                        AS shipments,
                  round(100.0 * avg(s.delivered_on_time::INT), 1) AS on_time_pct
           FROM shipments s
           JOIN carriers c ON s.carrier_id = c.carrier_id
           GROUP BY c.mode
           ORDER BY shipments DESC

columns: ["mode", "shipments", "on_time_pct"]
rows:
  ["LTL",        1250, 88.0]
  ["Intermodal", 1250, 88.0]
  ["FTL",        1250, 88.0]
  ["Parcel",     1250, 88.0]
truncated: false
```

A DDL attempt is refused before it ever reaches the warehouse:

```
> run_sql: DROP TABLE shipments
SQLValidationError: Only read-only SELECT queries are allowed.
```

## Development

```bash
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"
pytest
ruff check .
```

The DuckDB sample data is regenerated deterministically with:

```bash
python sample_data/generate.py
```

## License

MIT — see [LICENSE](LICENSE).
