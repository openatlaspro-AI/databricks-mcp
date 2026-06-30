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
