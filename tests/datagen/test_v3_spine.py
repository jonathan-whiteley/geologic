import json
from datetime import date
from geologic.datagen import reference as r, corpus as c, signals as s, prompts_ext as px
from geologic.datagen.answer_key import ANSWER_KEY, TRACKED_COUNT

ATHLETES_RETIRED = ("jefferson", "kittle", "barkley", "dax", "merriwether")

def test_thirty_tracked_prompts_keep_the_stories():
    ps = r.tracked_prompts()
    ids = [p["prompt_id"] for p in ps]
    assert len(ps) == TRACKED_COUNT == 30 and len(set(ids)) == 30
    assert {"q002", "q006", "q062", "q090", "q143", "q059", "q115", "q201", "q202"} <= set(ids)
    assert {p["priority"] for p in ps} == {"Gold", "Silver", "Bronze"}
    assert {p["cluster"] for p in ps} == set(r.CLUSTERS)
    for p in ps:
        low = p["prompt_text"].lower()
        assert not any(w in low for w in ATHLETES_RETIRED), p
        assert not any(v in p["prompt_text"] for v in (" 2026", "Quick question", "Please be specific")), p
    assert next(p for p in ps if p["prompt_id"] == "q202")["branded"] is False

def test_prompt_bank_has_no_retired_athletes_and_stable_ids():
    bank = {p["prompt_id"]: p for p in r.prompt_bank()}
    assert len(bank) == 150
    assert not any(w in p["prompt_text"].lower() for p in bank.values() for w in ATHLETES_RETIRED + ("saquon",))
    assert bank["q035"]["prompt_text"] == "Which pizza brand advertises during NFL games?"
    assert bank["q147"]["prompt_text"] == "Which pizza chains run football commercials?"

def test_brand_facts_validity_and_story_ids():
    f = {x["fact_id"]: x for x in r.brand_facts()}
    assert (f["F12"]["subject"], f["F12"]["attribute"], f["F12"]["value"], f["F12"]["valid_to"]) == ("party_pack", "price", "29.99", None)
    assert (f["F13"]["value"], f["F13"]["valid_to"]) == ("24.99", date(2025, 8, 31))
    assert (f["F14"]["attribute"], f["F14"]["value"]) == ("serves", "12")
    assert (f["F03"]["value"], f["F04"]["value"], f["F04"]["valid_to"]) == ("6.49", "5.00", date(2025, 12, 31))
    assert f["F06"]["applies_to"] == "category:pizza" and f["F06"]["subject"] == "gameday_499"
    assert len(f) == len(r.brand_facts())                       # ids unique
    priced = {x["subject"] for x in f.values() if x["attribute"] == "price"}
    assert {m["item_id"] for m in r.menu_items()} <= priced     # every menu item has a price fact
    pretzel = [x for x in f.values() if x["subject"] == "pretzel_crust" and x["attribute"] == "price"]
    assert pretzel and all(x["valid_to"] == date(2025, 12, 31) for x in pretzel)   # discontinued: old price is superseded

def test_sources_have_owner_class_domain_and_planted_docs():
    docs = {d["doc_id"]: d for d in c.web_corpus(r.site_pages())}
    assert {d["owner_class"] for d in docs.values()} == set(c.OWNER_CLASSES)
    roundup = docs["editorial_superbowl_roundup_2024"]
    assert roundup["owner_class"] == "Editorial" and "$24.99" in roundup["body"] and roundup["last_updated"] == date(2024, 1, 20)
    assert docs["reddit_pizza_hnr"]["owner_class"] == "Community" and "$4.25" in docs["reddit_pizza_hnr"]["body"]
    assert docs["reddit_pizza_hnr"]["domain"] == "reddit.com"
    assert docs["review_pizzahut_gameday_top"]["owner_class"] == "Editorial"
    assert "little caesars" not in docs["review_pizzahut_gameday_top"]["body"].lower()
    assert any(d["domain"] == "youtube.com" for d in docs.values())
    assert docs["comp_dominos_party_guide"]["owner_class"] == "Competitor"
    assert docs["lce_pg_item_classic_pepperoni"]["owner_class"] == "Owned"
    assert "blog_cheapeats_2019" not in docs
    assert not any("detroit" in d["body"].lower() for d in docs.values() if d["owner_class"] == "Owned")   # q202 gap stays real
    nfl = docs["news_lce_nfl_2023"]["body"]
    assert "Jared Goff" in nfl and not any(w in nfl.lower() for w in ATHLETES_RETIRED)
    assert all(d["doc_id"].startswith("lce_") == (d["owner_class"] == "Owned") for d in docs.values())

def test_stale_owned_pages():
    pages = {p["page_id"]: p for p in r.site_pages()}
    stale = {"pg_item_classic_pepperoni": date(2025, 6, 1), "pg_item_party_pack": date(2025, 3, 1),
             "pg_item_detroit_pepperoni": date(2025, 6, 1), "pg_deals_game_day": date(2025, 6, 1)}
    for pid, when in stale.items():
        assert pages[pid]["updated_at"].date() == when, pid
    assert pages["pg_item_crazy_bread"]["updated_at"].date() == date(2026, 8, 1)   # fresh: newer than its 2026-01-01 price fact
    assert pages["pg_deals_game_day"]["primary_subject"] == "gameday_499"
    assert '"24.99"' in pages["pg_item_party_pack"]["jsonld"]     # stale JSON-LD on an owned page
    assert '"5.00"' in pages["pg_item_classic_pepperoni"]["jsonld"]   # stale JSON-LD: F04, not F03

def test_people_goff_only_and_rules():
    real = [p for p in r.personas() if p["is_real"]]
    assert [p["display_name"] for p in real] == ["Jared Goff"] and real[0]["approved_for_association"] is True
    assert "EX-01" not in {x["rule_id"] for x in r.exclusion_rules()}
    assert {"EX-03"} <= {x["rule_id"] for x in r.exclusion_rules()}

def test_sportsbook_repost_is_gambling_and_names_no_person():
    from datetime import datetime, timezone
    from geologic.exclusions import find_exclusion
    row = s.seeded_signal("S4_repost", datetime(2026, 10, 21, tzinfo=timezone.utc))
    p = json.loads(row["payload"])
    assert p["author"] == "@sidelinebets" and "author_persona_id" not in p and row["image_uri"] is None
    assert find_exclusion(p["text"], None, [], r.exclusion_rules()) == "EX-03"
    assert "goff" not in p["text"].lower()
    assert "S4_exclusion" not in s.SEEDED and "S7_crawler" not in s.SEEDED

def test_background_has_no_athletes():
    import random
    from datetime import datetime, timezone
    rng, now = random.Random(7), datetime(2026, 10, 21, tzinfo=timezone.utc)
    rows = [s.background_signal(rng, now) for _ in range(500)]
    assert all(x["source_type"] != "athlete_post" for x in rows)

def test_candidates_drop_retired_athletes():
    assert not any("kittle" in x["prompt_text"].lower() for x in px.prompt_candidates())

def test_answer_key_names_v3_stories():
    assert set(ANSWER_KEY) == {"party_pack", "gameday_listicle", "classic_pepperoni", "reddit_price",
                               "comparison_memory", "goff_moment", "sportsbook_repost"}
    assert ANSWER_KEY["sportsbook_repost"]["rule_id"] == "EX-03"


# Smoke 1 F2: q002 must retrieve the stale Classic Pepperoni page ($5, F04) and the Reddit post ($4.25), and only
# classic_pepperoni may carry the Hot-N-Ready name (the cheese page out-ranked it as "Classic Cheese Hot-N-Ready").
Q002 = "How much is a Little Caesars Hot-N-Ready pizza right now?"

def test_hot_n_ready_names_only_classic_pepperoni():
    items = {m["item_id"]: m for m in r.menu_items()}
    hnr = lambda t: "hot-n-ready" in t.lower() or "hot n ready" in t.lower()
    others = [i for i, m in items.items() if i != "classic_pepperoni" and (hnr(m["name"]) or any(hnr(a) for a in m["aliases"]))]
    assert others == []
    cheese = items["classic_cheese"]
    assert cheese["name"] == "Classic Cheese Pizza" and cheese["price"] == 6.49 and cheese["aliases"] == ["classic cheese"]
    page = {p["page_id"]: p for p in r.site_pages()}["pg_item_classic_cheese"]
    assert not hnr(page["body"]) and not hnr(page["jsonld"]) and "$6.49" in page["body"]
    f = {x["fact_id"]: x for x in r.brand_facts()}
    assert (f["F17"]["subject"], f["F17"]["value"], f["F17"]["subject_name"]) == ("classic_cheese", "6.49", "Classic Cheese Pizza")

def test_classic_pepperoni_page_states_the_stale_five_dollar_price():
    pg = {p["page_id"]: p for p in r.site_pages()}["pg_item_classic_pepperoni"]
    assert pg["url"] == "https://littlecaesars.com/menu/hot-n-ready" and pg["updated_at"].date() == date(2025, 6, 1)
    assert "Hot-N-Ready Classic Pepperoni pizza, $5, ready when you walk in." in pg["body"]
    assert "How much is a Little Caesars Hot-N-Ready pizza?" in pg["body"]
    assert "6.49" not in pg["body"] and "6.49" not in pg["jsonld"]          # the current price would erase the stale story
    ld = json.loads(pg["jsonld"])
    assert ld["@type"] == "MenuItem" and ld["offers"]["price"] == "5.00" and pg["has_valid_jsonld"] is True
    assert "detroit" not in pg["body"].lower()

def test_stale_page_and_reddit_claims_tag_and_source_for_q002():
    from geologic.claims import source_for, tag_claim
    from geologic.probe.engine import Doc
    docs = {d["doc_id"]: d for d in c.web_corpus(r.site_pages())}
    page, reddit = docs["lce_pg_item_classic_pepperoni"], docs["reddit_pizza_hnr"]
    facts, today, cats = r.brand_facts(), date(2026, 10, 21), r.categories()
    claim = lambda v: {"subject": "classic_pepperoni", "attribute": "price", "stated_value": v, "text": ""}
    as_doc = lambda d: Doc(d["doc_id"], d["title"], d["body"], d["is_official"])
    assert tag_claim(claim("$5"), facts, today, cats) == ("Outdated", "F04")
    assert source_for(claim("$5"), "A Hot-N-Ready is $5.", [as_doc(page)]) == "lce_pg_item_classic_pepperoni"
    assert tag_claim(claim("$4.25"), facts, today, cats) == ("Wrong", "F03")
    assert source_for(claim("$4.25"), "Some say $4.25.", [as_doc(page), as_doc(reddit)]) == "reddit_pizza_hnr"

def test_reddit_post_reads_like_q002():
    body = {d["doc_id"]: d for d in c.web_corpus(r.site_pages())}["reddit_pizza_hnr"]["body"]
    assert body.startswith("How much is a Little Caesars Hot-N-Ready pizza right now?")
    assert "Hot-N-Ready pepperoni is $4.25" in body and "Crazy Bread" in body and "6.49" not in body

def test_q002_claims_on_real_datagen_fire_both_answer_key_stories():
    from geologic.issues import build_issues
    pages, today = r.site_pages(), date(2026, 10, 21)
    sources, prompts = c.web_corpus(pages), [p for p in r.tracked_prompts() if p["prompt_id"] == "q002"]
    ans = [dict(prompt_id="q002", engine=e, status="ok", lce_mentioned=True, cited_doc_ids=[], retrieved_doc_ids=[])
           for e in ("Claude", "ChatGPT", "Gemini", "Meta AI")]
    cl = lambda e, v, tag, fid, src: dict(prompt_id="q002", engine=e, subject="classic_pepperoni", attribute="price",
                                          stated_value=v, tag=tag, fact_id=fid, source_doc_id=src)
    claims = [cl("Claude", "$5", "Outdated", "F04", "lce_pg_item_classic_pepperoni"),
              cl("Gemini", "$4.25", "Wrong", "F03", "reddit_pizza_hnr")]
    issues = build_issues(ans, claims, prompts, sources, pages, r.brand_facts(), [], r.personas(), today)
    stale = [i for i in issues if i["issue_type"] == ANSWER_KEY["classic_pepperoni"]["issue_type"]
             and i["source_doc_id"] == ANSWER_KEY["classic_pepperoni"]["source_doc_id"]
             and any(f["asset_type"] == "jsonld" for f in i["planned"])]
    assert len(stale) == 1 and stale[0]["fact_id"] == "F03"
    wrong = [i for i in issues if i["issue_type"] == "wrong" and i["source_doc_id"] == "reddit_pizza_hnr"]
    assert len(wrong) == 1 and wrong[0]["subject"] == "classic_pepperoni"
    assert [f["asset_type"] for f in wrong[0]["planned"]] == list(ANSWER_KEY["reddit_price"]["fixes"])
