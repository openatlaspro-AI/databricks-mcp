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
