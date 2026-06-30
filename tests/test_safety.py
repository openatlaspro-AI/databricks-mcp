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


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM read_text('/etc/passwd')",
        "SELECT * FROM read_csv('/etc/passwd')",
        "SELECT * FROM read_parquet('/secret/data.parquet')",
        "SELECT * FROM glob('/**')",
        "SELECT content FROM read_blob('/etc/hosts')",
    ],
)
def test_filesystem_functions_are_blocked(sql):
    with pytest.raises(SQLValidationError):
        validate_and_rewrite(sql, max_rows=1000)


def test_trailing_semicolon_is_fine():
    out = validate_and_rewrite("SELECT 1 AS a;", max_rows=10)
    assert "LIMIT 10" in out.upper()
