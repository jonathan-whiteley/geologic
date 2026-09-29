import pytest
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

@pytest.mark.parametrize("text,expected", [
    # explicit brand name
    ("What is on the Little Caesars menu?", True),
    ("little caesars deals today", True),
    # trademark product names (no brand text)
    ("are crazy puffs worth it", True),
    ("What is a hot-n-ready pizza?", True),
    ("does hot n ready come with crazy bread?", True),
    ("how does the pizza portal work?", True),
    ("extramostbestest pepperoni review", True),
    ("extra most bestest or regular?", True),
    ("caesar wings calories", True),
    ("is crazy sauce vegan", True),
    ("slices-n-stix vs crazy bread", True),
    ("slices n stix review", True),
    # generic -- not branded
    ("best cheap pizza for a party", False),
    ("how many pizzas for 12 people?", False),
    ("which pizza chain is fastest for delivery?", False),
    ("best pizza for super bowl party", False),
    ("domino's vs pizza hut", False),
    # case-insensitive checks
    ("CRAZY PUFFS taste test", True),
    ("HOT-N-READY pizza review", True),
])
def test_is_branded(text, expected):
    assert r.is_branded(text) == expected


def test_prompt_bank_branded_counts():
    pb = r.prompt_bank()
    branded = [p for p in pb if p["branded"]]
    unbranded = [p for p in pb if not p["branded"]]
    # All rows must carry the column; total is 150
    assert all("branded" in p for p in pb)
    assert len(pb) == 150
    # Pinned range: unbranded count with trademark-term expansion is roughly 50-65
    assert 50 <= len(unbranded) <= 65, f"Expected 50-65 unbranded, got {len(unbranded)}"
    # Key invariant: product prompts with LCE trademark items should be branded
    hnr = next(p for p in pb if "hot-n-ready" in p["prompt_text"].lower()
               or "hot n ready" in p["prompt_text"].lower())
    assert hnr["branded"] is True
    # Generic game-day prompts should be unbranded
    generic = next(p for p in pb if "how many pizzas for 12 people" in p["prompt_text"].lower())
    assert generic["branded"] is False


def test_calendar_relative_to_now():
    now = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
    cal = {c["window_id"]: c for c in r.demand_calendar(now)}
    assert cal["fantasy_draft"]["start_ts"] <= now <= cal["fantasy_draft"]["end_ts"]
    assert cal["tnf"]["start_ts"] > now
