from geologic.config import Settings


def test_fq_and_env_override(monkeypatch):
    monkeypatch.setenv("GEOLOGIC_SCHEMA", "geologic_test")
    s = Settings.from_env()
    assert s.catalog == "jdub_demo"
    assert s.fq("menu_items") == "jdub_demo.geologic_test.menu_items"
    assert set(s.engines) == {"Claude", "Llama", "ChatGPT", "Gemma"}
    assert s.volume_path == "/Volumes/jdub_demo/geologic_test/assets"
