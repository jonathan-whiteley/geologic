from geologic.harness import check


def good_state():
    opp = lambda **k: {"status": "open", "signal_ids": [], "item_id": None, "cluster": None, "persona_id": None, **k}
    return {
        "opps": [opp(opp_type="accuracy_fix", page_id="pg_item_classic_pepperoni", item_id="classic_pepperoni", rank=1),
                 opp(opp_type="content_gap", page_id="pg_deals_game_day", cluster="game_day_party", rank=2),
                 opp(opp_type="content_gap", page_id="pg_about", cluster="sponsorship", rank=3),
                 opp(opp_type="persona_moment", page_id="pg_item_detroit_pepperoni", item_id="detroit_pepperoni", persona_id="p_goff", rank=4, signal_ids=["k"]),
                 opp(opp_type="trend", page_id="pg_item_crazy_puffs_pepperoni", item_id="crazy_puffs_pepperoni", rank=5),
                 opp(opp_type="crawler_gap", page_id="pg_order", rank=6),
                 opp(opp_type="trend", page_id="pg_item_pretzel_crust", item_id="pretzel_crust", rank=7, status="monitor")],
        "signals": [{"signal_id": "x", "producer": "seeded", "persona_id": "p_fictional_dax", "quarantined": True, "quarantine_rule_id": "EX-01"}],
        "suggestions": [{"opp_type": "accuracy_fix", "page_id": "pg_item_classic_pepperoni", "tier": "T0"},
                        {"opp_type": "accuracy_fix", "page_id": "pg_item_classic_pepperoni", "tier": "T1"},
                        {"opp_type": "content_gap", "page_id": "pg_deals_game_day", "tier": "T1"},
                        {"opp_type": "persona_moment", "page_id": "pg_item_detroit_pepperoni", "tier": "T2"},
                        {"opp_type": "content_gap", "page_id": "pg_about", "tier": "T0"},
                        {"opp_type": "content_gap", "page_id": "pg_about", "tier": "T1"},
                        {"opp_type": "crawler_gap", "page_id": "pg_order", "tier": "T0"}],
        "audits": [{"exclusion_rule_id": "EX-01", "enforcement_point": p} for p in ("ingest", "suggest", "publish")],
        "public_signal_ids": {"k"},
    }


def test_good_state_passes():
    assert check(good_state()) == []


def test_missing_enforcement_point():
    s = good_state(); s["audits"] = s["audits"][:2]
    assert any("S4" in f and "publish" in f for f in check(s))


def test_s5_order():
    s = good_state()
    next(o for o in s["opps"] if o["item_id"] == "pretzel_crust")["rank"] = 1
    assert any("S5" in f for f in check(s))


def test_quarantined_leak():
    s = good_state(); s["public_signal_ids"].add("x")
    assert any("S4" in f and "public" in f for f in check(s))


def test_metric_must_improve_after_publish():
    s = good_state(); s["accuracy_by_run"] = {"baseline": 0.7, "latest": 0.6}
    assert any("S1" in f for f in check(s))


def test_wrong_tier():
    s = good_state(); s["suggestions"][3]["tier"] = "T1"
    assert any("S3" in f for f in check(s))
