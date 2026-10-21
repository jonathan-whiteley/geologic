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


# Smoke 1 F3b: with no image match, a persona moment may pass on text resolution (menu_item_id set and
# resolution_confidence >= 0.9). The image match stays the preferred path, and the moment records which path matched.
def _goff(**kw):
    return sig(signal_id="g", source_type="athlete_post", persona_id="p_goff", is_real_persona=True,
               menu_item_id="detroit_pepperoni", reach=1_600_000, **kw)

def test_persona_moment_passes_on_text_resolution_without_image_match():
    ms = build_moments([_goff(image_match_score=None, resolution_confidence=0.95)], personas(), menu_items())
    assert [(m["kind"], m["item_id"], m["persona_id"], m["match_path"], m["image_match"]) for m in ms] == \
        [("persona", "detroit_pepperoni", "p_goff", "text", None)]

def test_low_confidence_text_resolution_without_image_match_drops_the_moment():
    assert build_moments([_goff(image_match_score=None, resolution_confidence=0.85)], personas(), menu_items()) == []
    assert build_moments([_goff(image_match_score=None)], personas(), menu_items()) == []   # no confidence at all

def test_image_match_is_the_preferred_path():
    ms = build_moments([_goff(image_match_score=0.585, resolution_confidence=0.95)], personas(), menu_items())
    assert ms[0]["match_path"] == "image" and ms[0]["image_match"] == 0.585

def test_text_path_never_rescues_quarantined_or_fictional_posts():
    assert build_moments([_goff(image_match_score=None, resolution_confidence=0.95, quarantined=True)], personas(), menu_items()) == []
    s = _goff(image_match_score=None, resolution_confidence=0.95); s["is_real_persona"] = False
    assert build_moments([s], personas(), menu_items()) == []
