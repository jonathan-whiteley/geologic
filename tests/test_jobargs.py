import os, sys, pytest
from geologic import jobargs

@pytest.fixture
def env(monkeypatch):
    fake = {}
    monkeypatch.setattr(os, "environ", fake)
    return fake

def test_apply_strips_flags_and_sets_env(env, monkeypatch):
    monkeypatch.delitem(sys.modules, "geologic.config", raising=False)
    argv = ["run_probe.py", "--catalog", "jdub_demo", "--schema=geologic_v3", "--lakebase-db", "geologic_v3", "--mode", "full"]
    assert jobargs.apply(argv) == ["run_probe.py", "--mode", "full"]
    assert argv == ["run_probe.py", "--mode", "full"]
    env.pop("PYTEST_CURRENT_TEST", None)   # pytest itself writes this key into os.environ (here: the fake)
    assert env == {"GEOLOGIC_CATALOG": "jdub_demo", "GEOLOGIC_SCHEMA": "geologic_v3", "LAKEBASE_DB": "geologic_v3"}

def test_apply_missing_value_exits(env):
    with pytest.raises(SystemExit):
        jobargs.apply(["x.py", "--schema"])

def test_apply_after_config_import_compares_loaded_settings(env):
    import geologic.config as cfg   # already imported by other tests (or imported here with the empty env); apply() must notice
    loaded = cfg.settings.schema
    with pytest.raises(RuntimeError):
        jobargs.apply(["x.py", "--schema", loaded + "_other"])   # env var never set, settings loaded: still refused
    assert "GEOLOGIC_SCHEMA" not in env
    jobargs.apply(["x.py", "--schema", loaded])                  # same value as the loaded settings: fine
    assert env["GEOLOGIC_SCHEMA"] == loaded
    env["LAKEBASE_DB"] = "geologic_v3"
    with pytest.raises(RuntimeError):
        jobargs.apply(["x.py", "--lakebase-db", "geologic"])     # Lakebase db is compared against the env var
