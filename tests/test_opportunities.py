from datetime import datetime, timezone
from geologic.datagen.reference import menu_items, prompt_bank, demand_calendar
from geologic.opportunities import build

NOW = datetime(2026, 9, 24, 9, 0, tzinfo=timezone.utc)
MENU, PROMPTS, CAL = menu_items(), prompt_bank(), demand_calendar(NOW)
P = {p["prompt_id"]: p for p in PROMPTS}

def resp(pid, mentioned, rank, claims=()):
    return {"prompt_id": pid, "engine": "Claude", "status": "ok", "lce_mentioned": mentioned, "lce_rank": rank, "claims": list(claims)}

def ids(cluster, n=3):
    return [p["prompt_id"] for p in PROMPTS if p["cluster"] == cluster][:n]

def sig(**kw):
    base = dict(signal_id="s", source_type="social", velocity=None, reach=100, hits=None, page=None, menu_item_id=None,
                persona_id=None, is_real_persona=False, image_match_score=None, resolution_confidence=0.95, quarantined=False)
    base.update(kw); return base

RESP = ([resp(i, True, 1, [{"item": "Hot-N-Ready", "price": "$5", "verdict": "wrong"}]) for i in ids("value")] +
        [resp(i, False, None) for i in ids("game_day_party")] + [resp(i, False, None) for i in ids("sponsorship")] +
        [resp(i, True, 1) for i in ids("product")])
SIGS = [sig(signal_id="k", source_type="athlete_post", menu_item_id="detroit_pepperoni", persona_id="p_kittle", is_real_persona=True, image_match_score=0.93, resolution_confidence=0.93),
        sig(signal_id="x", persona_id="p_fictional_dax", quarantined=True, menu_item_id="classic_pepperoni"),
        sig(signal_id="pz", velocity=7.9, reach=6400, menu_item_id="pretzel_crust"),
        sig(signal_id="pf", velocity=4.2, reach=1800, menu_item_id="crazy_puffs_pepperoni"),
        sig(signal_id="c", source_type="crawler_hit", page="/order", hits=0)]
OPPS = build(RESP, PROMPTS, MENU, CAL, SIGS, NOW)
BY = {o["opp_type"] + ":" + (o["item_id"] or o["page_id"] or ""): o for o in OPPS}

def test_s1_accuracy_fix():
    o = BY["accuracy_fix:classic_pepperoni"]
    assert o["page_id"] == "pg_item_classic_pepperoni" and o["assets"] == ["jsonld", "faq"] and o["gap_severity"] == 1.0

def test_s2_s6_content_gaps_with_windows():
    gd = BY["content_gap:pg_deals_game_day"]
    assert gd["window_expires_at"] is not None and gd["cluster"] == "game_day_party"
    assert gd["question_volume"] > 0
    assert BY["content_gap:pg_about"]["assets"] == ["jsonld", "faq"]

def test_s3_persona_moment_is_visual():
    o = BY["persona_moment:detroit_pepperoni"]
    assert o["persona_id"] == "p_kittle" and o["visual_sourced"] is True and o["assets"] == ["alt_text"]

def test_s4_quarantined_never_appears():
    assert not any("x" in o["signal_ids"] for o in OPPS)

def test_s5_ranking():
    puffs, pretzel = BY["trend:crazy_puffs_pepperoni"], BY["trend:pretzel_crust"]
    assert puffs["rank"] < pretzel["rank"] and pretzel["status"] == "monitor"

def test_s7_crawler_gap():
    assert BY["crawler_gap:pg_order"]["assets"] == ["jsonld"]

def test_healthy_cluster_has_no_gap():
    assert "content_gap:pg_menu" not in BY
