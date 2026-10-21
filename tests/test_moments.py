from geologic.datagen.reference import menu_items, personas
from geologic.moments import build_moments, parse_questions, link_questions, fallback_question

def sig(**kw):
    base = dict(signal_id="s", source_type="social", quarantined=False, menu_item_id=None, persona_id=None, is_real_persona=False,
                image_match_score=None, reach=10, velocity=None)
    return {**base, **kw}

def test_build_groups_persona_posts_and_trends_and_skips_quarantine():
    sigs = [sig(signal_id="g1", source_type="athlete_post", persona_id="p_goff", is_real_persona=True, menu_item_id="detroit_pepperoni",
                image_match_score=0.91, reach=1_600_000),
            sig(signal_id="g2", source_type="athlete_post", persona_id="p_goff", is_real_persona=True, menu_item_id="detroit_pepperoni",
                image_match_score=0.88, reach=900),
            sig(signal_id="t1", velocity=4.2, menu_item_id="crazy_puffs_pepperoni", reach=1800),
            sig(signal_id="q1", velocity=6.5, menu_item_id="detroit_pepperoni", quarantined=True),   # the sportsbook repost
            sig(signal_id="n1", velocity=1.0, menu_item_id="crazy_bread")]
    ms = {m["kind"] + ":" + m["item_id"]: m for m in build_moments(sigs, personas(), menu_items())}
    assert set(ms) == {"persona:detroit_pepperoni", "trend:crazy_puffs_pepperoni"}
    g = ms["persona:detroit_pepperoni"]
    assert g["signal_ids"] == ["g1", "g2"] and g["reach"] == 1_600_000 and g["image_match"] == 0.91 and g["persona_id"] == "p_goff"
    assert g["title"] == "Jared Goff posted a Detroit-Style Deep!Deep! Dish Pepperoni moment"
    assert all("q1" not in m["signal_ids"] for m in ms.values())

def test_parse_questions():
    assert parse_questions('```json\n["What pizza did Jared Goff post?", "Detroit-style pizza for game day", "third"]\n```') == \
        ["What pizza did Jared Goff post?", "Detroit-style pizza for game day"]
    assert parse_questions("not json") == [] and parse_questions('{"a": 1}') == []
    assert "\u2014" not in parse_questions('["Detroit pizza \u2014 game day"]')[0]
    assert fallback_question("Crazy Bread") == "Where can I get Crazy Bread?"

def test_link_threshold_boundary():
    scores = {"Detroit-style pizza for game day": {"id": "q202", "kind": "tracked", "score": 0.80},
              "What pizza did Jared Goff post?": {"id": "q057", "kind": "tracked", "score": 0.79}}
    ids, new = link_questions(list(scores), scores.get, 0.80)
    assert ids[0] == "q202" and ids[1].startswith("s_") and new == [(ids[1], "What pizza did Jared Goff post?")]

def test_link_reuses_matching_suggestion_and_dedupes():
    hit = {"id": "c004", "kind": "suggested", "score": 0.93}
    ids, new = link_questions(["a", "b"], lambda t: hit, 0.80)
    assert ids == ["c004"] and new == []
    assert link_questions(["x"], lambda t: None, 0.80)[0][0].startswith("s_")
