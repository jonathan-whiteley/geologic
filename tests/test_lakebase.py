from geologic.lakebase import TokenCache

def test_token_cache_refreshes_after_ttl():
    t = [0.0]; minted = []
    def mint():
        minted.append(1); return f"tok{len(minted)}"
    c = TokenCache(mint, ttl_s=100, clock=lambda: t[0])
    assert c.get() == "tok1" and c.get() == "tok1"
    t[0] = 101
    assert c.get() == "tok2" and len(minted) == 2
