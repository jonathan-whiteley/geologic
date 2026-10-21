from geologic.lakebase import TokenCache

def test_token_cache_refreshes_after_ttl():
    t = [0.0]; minted = []
    def mint():
        minted.append(1); return f"tok{len(minted)}"
    c = TokenCache(mint, ttl_s=100, clock=lambda: t[0])
    assert c.get() == "tok1" and c.get() == "tok1"
    t[0] = 101
    assert c.get() == "tok2" and len(minted) == 2

def test_user_falls_back_to_app_client_id(monkeypatch):
    import geologic.lakebase as L
    monkeypatch.delenv("LAKEBASE_USER", raising=False)
    monkeypatch.setenv("DATABRICKS_CLIENT_ID", "sp-123")
    assert L.lakebase_user() == "sp-123"
    monkeypatch.setenv("LAKEBASE_USER", "me@x.com")
    assert L.lakebase_user() == "me@x.com"
