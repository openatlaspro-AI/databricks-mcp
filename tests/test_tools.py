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
