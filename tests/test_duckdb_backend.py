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
    # max_rows is the backend safety cap: a query that yields more rows than the
    # cap is reported as truncated. Here 3 rows are available but only 2 returned.
    res = backend.run_query("SELECT * FROM shipments LIMIT 3", max_rows=2)
    assert res.row_count == 2
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
