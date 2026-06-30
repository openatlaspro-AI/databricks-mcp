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
