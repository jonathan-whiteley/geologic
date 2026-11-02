from datetime import datetime, timezone
from geologic.datagen.reference import menu_items, prompt_bank, demand_calendar, personas
from geologic.opportunities import build

NOW = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
MENU, PROMPTS, CAL = menu_items(), prompt_bank(), demand_calendar(NOW)
PERSONAS = personas()
P = {p["prompt_id"]: p for p in PROMPTS}

def resp(pid, mentioned, rank, claims=(), cites_official=False):
    return {"prompt_id": pid, "engine": "Claude", "status": "ok", "lce_mentioned": mentioned,
            "lce_rank": rank, "claims": list(claims), "cites_official": cites_official}

def ids(cluster, n=3):
    return [p["prompt_id"] for p in PROMPTS if p["cluster"] == cluster][:n]

def sig(**kw):
    base = dict(signal_id="s", source_type="social", velocity=None, reach=100, hits=None, page=None, menu_item_id=None,
                persona_id=None, is_real_persona=False, image_match_score=None, resolution_confidence=0.95, quarantined=False)
    base.update(kw); return base

# sponsorship responses: LCE mentioned (for citation_gap S6), no official citation.
RESP = ([resp(i, True, 1, [{"item": "Hot-N-Ready", "price": "$5", "verdict": "wrong"}]) for i in ids("value")] +
        [resp(i, False, None) for i in ids("game_day_party")] +
        [resp(i, True, 1) for i in ids("sponsorship")] +
        [resp(i, True, 1, cites_official=True) for i in ids("product")])
SIGS = [sig(signal_id="k", source_type="athlete_post", menu_item_id="detroit_pepperoni", persona_id="p_kittle", is_real_persona=True, image_match_score=0.93, resolution_confidence=0.93),
        sig(signal_id="x", persona_id="p_fictional_dax", quarantined=True, menu_item_id="classic_pepperoni"),
        sig(signal_id="pz", velocity=7.9, reach=6400, menu_item_id="pretzel_crust"),
        sig(signal_id="pf", velocity=4.2, reach=1800, menu_item_id="crazy_puffs_pepperoni"),
        sig(signal_id="c", source_type="crawler_hit", page="/order", hits=0)]
OPPS = build(RESP, PROMPTS, MENU, CAL, SIGS, NOW, personas=PERSONAS)
BY = {o["opp_type"] + ":" + (o["item_id"] or o["page_id"] or ""): o for o in OPPS}

def test_s1_accuracy_fix():
    o = BY["accuracy_fix:classic_pepperoni"]
    assert o["page_id"] == "pg_item_classic_pepperoni" and o["assets"] == ["jsonld", "faq"] and o["gap_severity"] == 1.0

def test_s2_content_gap_with_window():
    # S6 is now citation_gap:pg_about; this test covers S2 only.
    gd = BY["content_gap:pg_deals_game_day"]
    assert gd["window_expires_at"] is not None and gd["cluster"] == "game_day_party"
    assert gd["question_volume"] > 0

def test_s3_persona_moment_is_visual():
    o = BY["persona_moment:detroit_pepperoni"]
    assert o["persona_id"] == "p_kittle" and o["visual_sourced"] is True and o["assets"] == ["alt_text"]
    assert "George Kittle" in o["title"]

def test_s4_quarantined_never_appears():
    assert not any("x" in o["signal_ids"] for o in OPPS)

def test_s5_ranking():
    puffs, pretzel = BY["trend:crazy_puffs_pepperoni"], BY["trend:pretzel_crust"]
    assert puffs["rank"] < pretzel["rank"] and pretzel["status"] == "monitor"

def test_s6_citation_gap():
    # sponsorship: mention_rate=1.0 >= 0.5, official_rate=0.0 < 0.6 -> citation_gap on pg_about
    o = BY["citation_gap:pg_about"]
    assert o["cluster"] == "sponsorship"
    assert o["gap_severity"] > 0 and o["assets"] == ["jsonld", "faq"]
    assert "NFL" in o["title"]

def test_s7_crawler_gap():
    assert BY["crawler_gap:pg_order"]["assets"] == ["jsonld"]

def test_s7_crawler_gap_dedup():
    # Two crawler_hit signals for the same page produce exactly one opportunity with both signal_ids aggregated.
    sigs2 = [sig(signal_id="c1", source_type="crawler_hit", page="/order", hits=0),
             sig(signal_id="c2", source_type="crawler_hit", page="/order", hits=0)]
    opps2 = build([], PROMPTS, MENU, CAL, sigs2, NOW, personas=PERSONAS)
    crawler_opps = [o for o in opps2 if o["opp_type"] == "crawler_gap" and o["page_id"] == "pg_order"]
    assert len(crawler_opps) == 1
    assert set(crawler_opps[0]["signal_ids"]) == {"c1", "c2"}

def test_no_citation_gap_when_official_rate_high():
    # game_day_party with 100% official citation rate: no citation_gap should fire.
    pids = ids("game_day_party")
    high_resp = [resp(p, True, 1, cites_official=True) for p in pids]
    opps_ho = build(high_resp, PROMPTS, MENU, CAL, [], NOW, personas=PERSONAS)
    assert not any(o["opp_type"] == "citation_gap" and o.get("cluster") == "game_day_party" for o in opps_ho)

def test_healthy_cluster_has_no_gap():
    assert "content_gap:pg_menu" not in BY

# The bank has no unbranded product prompts (only tracked candidates can), so add synthetic ones.
PROD_PROMPTS = PROMPTS + [dict(prompt_id=f"cand_prod{i}", prompt_text="x", cluster="product", base_volume=100, branded=False)
                          for i in range(3)]

def unbranded(cluster, n=3):
    return [p["prompt_id"] for p in PROD_PROMPTS if p["cluster"] == cluster and not p["branded"]][:n]

def test_cluster_gaps_have_distinct_ids_on_shared_page():
    # comparison and product both map to pg_menu; both failing must not collide on opp_id.
    bad = [resp(i, False, None) for c in ("comparison", "product") for i in unbranded(c)]
    opps = build(bad, PROD_PROMPTS, MENU, CAL, [], NOW, personas=PERSONAS)
    gaps = [o for o in opps if o["opp_type"] == "content_gap" and o["page_id"] == "pg_menu"]
    assert {o["cluster"] for o in gaps} == {"comparison", "product"}
    assert len({o["opp_id"] for o in gaps}) == 2
    cites = [resp(i, True, 1) for c in ("comparison", "product") for i in unbranded(c)]
    copps = [o for o in build(cites, PROD_PROMPTS, MENU, CAL, [], NOW, personas=PERSONAS)
             if o["opp_type"] == "citation_gap" and o["page_id"] == "pg_menu"]
    assert len(copps) == 2 and len({o["opp_id"] for o in copps}) == 2

def test_unknown_prompt_id_is_skipped():
    extra = RESP + [resp("cand_unknown", False, None, [{"item": "Hot-N-Ready", "price": "$5", "verdict": "wrong"}])]
    opps = build(extra, PROMPTS, MENU, CAL, SIGS, NOW, personas=PERSONAS)
    assert [o["opp_id"] for o in opps] == [o["opp_id"] for o in OPPS]

def test_null_reach_does_not_crash():
    sigs = [sig(signal_id="k2", source_type="athlete_post", menu_item_id="detroit_pepperoni", persona_id="p_kittle",
                is_real_persona=True, image_match_score=0.9, reach=None),
            sig(signal_id="t2", velocity=5.0, reach=None, menu_item_id="pretzel_crust")]
    opps = build([], PROMPTS, MENU, CAL, sigs, NOW, personas=PERSONAS)
    assert {o["opp_type"] for o in opps} >= {"persona_moment", "trend"}

def test_gap_reasoning_uses_cluster_label_not_key():  # O2
    gd = BY["content_gap:pg_deals_game_day"]
    assert " in Game-day / party sizing across " in gd["reasoning"] and "game_day_party" not in gd["reasoning"]
    assert gd["title"] == "Answer game day party questions"
    cg = BY["citation_gap:pg_about"]
    assert " in Sponsorship (NFL) with " in cg["reasoning"]
