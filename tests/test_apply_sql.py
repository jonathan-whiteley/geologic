import importlib.util, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("apply_sql", ROOT / "scripts" / "apply_sql.py")
aq = importlib.util.module_from_spec(spec); spec.loader.exec_module(aq)

V3 = {"catalog": "jdub_demo", "schema": "geologic_v3", "warehouse_id": "0168e23e24e6ae10"}

def test_v3_resolving_to_v3_schema_ok():
    assert aq.target_problem("v3", V3, allow_v2=False) is None

def test_v3_resolving_to_v2_schema_refused():
    assert "geologic_v3" in aq.target_problem("v3", dict(V3, schema="geologic"), allow_v2=False)
    assert aq.target_problem("v3", dict(V3, catalog="other"), allow_v2=False)

def test_dev_needs_allow_v2_and_unknown_target_refused():
    assert aq.target_problem("dev", dict(V3, schema="geologic"), allow_v2=False)
    assert aq.target_problem("dev", dict(V3, schema="geologic"), allow_v2=True) is None
    assert "unknown target" in aq.target_problem("prod", V3, allow_v2=False)

def test_main_refuses_before_running_anything(monkeypatch):
    calls = []
    monkeypatch.setattr(aq, "bundle_vars", lambda t: dict(V3, schema="geologic"))
    monkeypatch.setattr(aq, "execute", lambda *a: calls.append(a))
    assert aq.main(["--target", "v3", "--query", "SELECT 1"]) == 1 and calls == []
