import sys, pathlib, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
import apply_lakebase as A


def test_refuses_the_v2_database():
    assert A.target_problem("geologic") == "refusing the v2 database geologic" and A.target_problem("geologic_v3") is None


def test_grant_needs_a_client_id_before_interpolation():
    sql = A.grant_statements("00000000-0000-4000-8000-000000000000", "geologic_v3")
    assert sql[1] == "SELECT databricks_create_role('00000000-0000-4000-8000-000000000000', 'SERVICE_PRINCIPAL')"
    assert 'GRANT CONNECT ON DATABASE geologic_v3 TO "00000000-0000-4000-8000-000000000000"' in sql
    with pytest.raises(ValueError):
        A.grant_statements("x'); DROP ROLE admin; --", "geologic_v3")
    assert A.main(["--target", "v3", "--grant-sp", "not-an-id"]) == 1
