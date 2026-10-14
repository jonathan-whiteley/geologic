from geologic.config import Settings


def test_fq_and_env_override(monkeypatch):
    monkeypatch.setenv("GEOLOGIC_SCHEMA", "geologic_test")
    s = Settings.from_env()
    assert s.catalog == "jdub_demo"
    assert s.fq("menu_items") == "jdub_demo.geologic_test.menu_items"
    assert set(s.engines) == {"Claude", "ChatGPT", "Gemini", "Meta AI"}
    assert s.volume_path == "/Volumes/jdub_demo/geologic_test/assets"


def test_engine_lineup():
    from geologic.config import DEFAULT_ENGINES
    assert DEFAULT_ENGINES == {"Claude": "databricks-claude-sonnet-5-5", "ChatGPT": "databricks-gpt-5-5",
                               "Gemini": "databricks-gemini-3-8-flash", "Meta AI": "databricks-llama-4-maverick"}
