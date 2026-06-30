import pytest

from databricks_mcp.backends.duckdb_backend import DuckDBBackend


@pytest.fixture
def backend():
    return DuckDBBackend()
