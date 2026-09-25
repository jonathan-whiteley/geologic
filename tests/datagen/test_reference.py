from datetime import datetime, timezone
from geologic.datagen import reference as r

def test_menu_has_real_items_and_prices():
    names = {m["name"] for m in r.menu_items()}
    for n in ["Classic Pepperoni Hot-N-Ready", "Crazy Bread", "Crazy Puffs (Pepperoni)",
              "Detroit-Style Deep!Deep! Dish Pepperoni", "Caesar Wings (Buffalo)", "Pretzel Crust Pepperoni"]:
        assert n in names
    hnr = next(m for m in r.menu_items() if m["item_id"] == "classic_pepperoni")
    assert hnr["price"] == 6.49
    pretzel = next(m for m in r.menu_items() if m["item_id"] == "pretzel_crust")
    assert pretzel["available"] is False and pretzel["is_lto"] is True
    assert 25 <= len(r.menu_items()) <= 45

def test_gameday_deal():
    d = r.deals()
    assert any(x["price"] == 4.99 and x["channel"] == "online" for x in d)

def test_pages_seeded_gaps():
    pages = {p["page_id"]: p for p in r.site_pages()}
    assert 55 <= len(pages) <= 70
    hnr = pages[r.SEEDED_PAGE_IDS["hot_n_ready"]]
    assert hnr["jsonld"] is None and "$" not in hnr["body"]          # S1 gap
    gd = pages[r.SEEDED_PAGE_IDS["game_day"]]
    assert "how many" not in gd["body"].lower()                        # S2 gap
    assert all(p["version"] == 1 for p in pages.values())

def test_personas_real_never_excluded():
    ps = r.personas()
    real = {p["display_name"] for p in ps if p["is_real"]}
    assert real == {"Justin Jefferson", "George Kittle", "Jared Goff", "Saquon Barkley"}
    assert not any(p["is_real"] and p["is_excluded"] for p in ps)
    assert sum(p["is_excluded"] for p in ps) == 1

def test_prompt_bank_shape():
    pb = r.prompt_bank()
    assert len(pb) == 150
    assert {p["cluster"] for p in pb} == set(r.CLUSTERS)
    assert len({p["prompt_id"] for p in pb}) == 150
    assert any("how many pizzas" in p["prompt_text"].lower() for p in pb)
    assert any("official pizza" in p["prompt_text"].lower() for p in pb)

def test_calendar_relative_to_now():
    now = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    cal = {c["window_id"]: c for c in r.demand_calendar(now)}
    assert cal["fantasy_draft"]["start_ts"] <= now <= cal["fantasy_draft"]["end_ts"]
    assert cal["tnf"]["start_ts"] > now
