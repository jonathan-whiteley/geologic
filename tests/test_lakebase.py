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


def test_lakebase_db_defaults_to_v3(monkeypatch):   # final review I3
    import geologic.lakebase as L
    from types import SimpleNamespace as N
    assert L.LAKEBASE_DEFAULTS["LAKEBASE_DB"] == "geologic_v3" and L.LAKEBASE_DEFAULTS["LAKEBASE_INSTANCE"] == "geologic"
    monkeypatch.delenv("LAKEBASE_DB", raising=False)
    monkeypatch.setenv("LAKEBASE_HOST", "h"); monkeypatch.setenv("LAKEBASE_INSTANCE", "geologic"); monkeypatch.setenv("LAKEBASE_USER", "u")
    seen = []
    monkeypatch.setattr(L, "connect", lambda host, db, user, tok: seen.append(db))
    L.from_env(N(database=None))()
    assert seen == ["geologic_v3"]
