import sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import apply_lakebase as A


def test_refuses_the_v2_database():
    assert A.target_problem("geologic") == "refusing the v2 database geologic" and A.target_problem("geologic_v3") is None


def test_grant_needs_a_client_id_before_interpolation():
    sql = A.grant_statements("02b98af0-a7e5-43d9-8a99-ff61f7d3ce4c", "geologic_v3")
    assert sql[1] == "SELECT databricks_create_role('02b98af0-a7e5-43d9-8a99-ff61f7d3ce4c', 'SERVICE_PRINCIPAL')"
    assert 'GRANT CONNECT ON DATABASE geologic_v3 TO "02b98af0-a7e5-43d9-8a99-ff61f7d3ce4c"' in sql
    with pytest.raises(ValueError):
        A.grant_statements("x'); DROP ROLE admin; --", "geologic_v3")
    assert A.main(["--target", "v3", "--grant-sp", "not-an-id"]) == 1
