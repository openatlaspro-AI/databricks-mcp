# databricks-mcp — Design Spec

**Date:** 2026-06-30
**Status:** Approved (design), pending implementation plan
**Author:** Mark Teji (with Claude Code)

## Purpose

An open-source [Model Context Protocol](https://modelcontextprotocol.io) server that gives an AI
agent **safe, read-only analytics access to a SQL warehouse**. It ships with a bundled local DuckDB
sample warehouse so anyone can run it in ~30 seconds with zero setup, and connects to a real
**Databricks SQL Warehouse** via environment variables.

This is a portfolio project: it must be genuinely useful, genuinely runnable by a stranger, and
prove real skill — no fabricated capability. Every guardrail claim in the README is backed by a
passing test (the "receipts" ethos from `production-rag-eval`).

### Why it exists (hiring context)

Fills resume gaps for AI Engineer roles: **MCP authoring** (not just usage), **agent tool-use
design**, **Databricks**, **security best practices**, plus Python + tests + CI + open-source
presence — in one focused repo.

## Non-Goals (YAGNI)

- No write/DDL/DML capability — read-only by construction, forever.
- No auth server / multi-tenant access control — single-user, env-var credentials.
- No query builder UI or web frontend — it is an MCP server, driven by an agent.
- No support for warehouses beyond DuckDB (local) and Databricks SQL (remote) in v1.

## Architecture

Small, independently-testable units:

| Unit | Responsibility | Depends on |
|---|---|---|
| `server.py` | FastMCP server; registers tools; selects + wires the active backend | `tools.py`, `backends/`, MCP SDK |
| `backends/base.py` | `Backend` protocol: `list_tables`, `describe_table`, `sample_rows`, `run_query`, `profile_table` | — |
| `backends/duckdb_backend.py` | Default backend; loads bundled sample parquet into an in-memory/temp DuckDB | `duckdb` |
| `backends/databricks_backend.py` | Connects to a Databricks SQL Warehouse | `databricks-sql-connector` |
| `safety.py` | SQL guard: parse → validate → rewrite. The differentiator. | `sqlglot` |
| `sample_data/` | Synthetic logistics/freight parquet (shipments, lanes, carriers, invoices) | — |

**Backend selection:** `DB_BACKEND` env var (`duckdb` default | `databricks`). Databricks backend
reads `DATABRICKS_SERVER_HOSTNAME`, `DATABRICKS_HTTP_PATH`, `DATABRICKS_TOKEN`.

**Transport:** stdio (the MCP standard for local servers). HTTP transport is a possible later add,
out of scope for v1.

## MCP Tools

| Tool | Input | Output |
|---|---|---|
| `list_tables` | — | table names + schemas |
| `describe_table` | `table` | columns, types, row count |
| `sample_rows` | `table`, `n` (default 10, capped) | preview rows |
| `run_sql` | `query` | guarded read-only result rows (row-capped) |
| `profile_table` | `table` | per-column null %, distinct count, min/max |

All tool inputs/outputs are typed with `pydantic` models so the agent gets clean schemas.

## Safety Model (the differentiator)

Every query passed to `run_sql` (and the SQL the other tools generate internally) goes through
`safety.py`:

1. **Parse** with `sqlglot`. Reject anything that fails to parse.
2. **Single statement only** — reject multi-statement input (blocks stacked-query injection).
3. **Read-only allowlist** — permit only `SELECT`, CTE (`WITH`), and `EXPLAIN`. Reject any
   `INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/GRANT/COPY/CALL/PRAGMA/ATTACH`.
4. **System-table block** — deny references to `information_schema` internals / system catalogs
   beyond the curated `list_tables` path (configurable).
5. **Auto-LIMIT** — inject or clamp a `LIMIT` (default 1000, configurable via `MAX_ROWS`) so an
   agent can't pull unbounded data.
6. **Structured errors** — on rejection, return a clear reason the agent can act on, never the raw
   driver error.

Secrets only ever come from env vars; none are logged.

## Testing & Proof

- `pytest` suite covering: each tool happy-path (DuckDB), and a **guardrail table** asserting that
  DDL, DML, multi-statement, and unbounded queries are all rejected.
- A README example with a **recorded agent transcript** (Claude calling the tools against the
  sample warehouse).
- **GitHub Actions CI** runs the suite on push.

## Deliverables

- Public repo `openatlaspro-AI/databricks-mcp`, MIT license.
- `README.md`: 30-second quickstart (`uvx databricks-mcp`), Claude Desktop config snippet,
  Databricks setup section, guardrail explanation, recorded transcript.
- `pyproject.toml` packaged for `uvx` execution.
- CI workflow, tests, sample data.

## Resume Bullet Earned (honest, post-build)

> Built and published an open-source MCP server (Python, MCP SDK) giving AI agents safe, read-only
> analytics over Databricks SQL Warehouses and local DuckDB — SQL-AST validation (sqlglot) enforces
> read-only / single-statement / row-cap guardrails. Runnable via `uvx`, covered by pytest + CI.

## Open Questions

None — repo name (`databricks-mcp`) and sample dataset (synthetic logistics/freight) are decided.
