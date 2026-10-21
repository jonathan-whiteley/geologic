from geologic.datagen.reference import menu_items, personas
from geologic.moments import build_moments, parse_questions, link_questions, fallback_question, question_messages, suggestion_id, link_moment, item_prompt_ids

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


# Ruling S2-B (smoke 2 F-S2-1): the question prompt carries the post text, matching looks at k=5 hits and prefers a
# tracked prompt at or above the threshold over any suggestion, and a question never matches its own suggestion.
def test_question_messages_carry_the_signal_text():
    s = _goff(image_match_score=0.585, resolution_confidence=0.95, text="Detroit-style is back before kickoff. Corner piece is mine.")
    m = build_moments([s], personas(), menu_items())[0]
    assert m["signal_texts"] == ["Detroit-style is back before kickoff. Corner piece is mine."]
    user = question_messages(m, "Detroit-Style Deep!Deep! Dish Pepperoni", "Jared Goff")[1]["content"]
    assert "before kickoff" in user and "Jared Goff posted it" in user and "Detroit-Style Deep!Deep! Dish Pepperoni" in user
    assert "Post:" not in question_messages({"title": "Crazy Bread is trending"}, "Crazy Bread")[1]["content"]   # no text, no line

def test_link_prefers_a_tracked_prompt_over_a_closer_suggestion():
    hits = [{"id": "s_old", "kind": "suggested", "score": 0.97}, {"id": "q202", "kind": "tracked", "score": 0.82},
            {"id": "q057", "kind": "tracked", "score": 0.81}]
    ids, new = link_questions(["Best Detroit-style pizza before kickoff"], lambda t: hits, 0.80)
    assert ids == ["q202"] and new == []
    below = [{"id": "s_old", "kind": "suggested", "score": 0.97}, {"id": "q202", "kind": "tracked", "score": 0.79}]
    assert link_questions(["x"], lambda t: below, 0.80) == (["s_old"], [])   # no tracked prompt at threshold: the suggestion

def test_a_suggestion_never_matches_itself():
    q = "Is Little Caesars Detroit-Style Deep Dish any good?"
    own = suggestion_id(q)
    assert own == "s_" + __import__("hashlib").sha1(q.lower().encode()).hexdigest()[:10]   # the id the last build upserted
    hits = [{"id": own, "kind": "suggested", "score": 0.999}, {"id": "q057", "kind": "tracked", "score": 0.75}]
    assert link_questions([q], lambda t: hits, 0.80) == ([own], [(own, q)])   # re-proposed, not a match on itself
    hits = [{"id": own, "kind": "suggested", "score": 0.999}, {"id": "q202", "kind": "tracked", "score": 0.80}]
    assert link_questions([q], lambda t: hits, 0.80) == (["q202"], [])

def test_link_asks_for_five_hits_when_nearest_takes_k():
    seen = []
    def nearest(text, k=1):
        seen.append(k)
        return [{"id": "q202", "kind": "tracked", "score": 0.9}]
    assert link_questions(["a"], nearest, 0.80) == (["q202"], []) and seen == [5]


# Ruling S2-F: a moment also links every tracked prompt whose own text resolves to the moment's menu item through the
# alias resolver (facts.resolve_item; the same alias rule pipelines/signals.sql uses for signals, confidence 0.95).
TRACKED = [dict(prompt_id="q202", prompt_text="Best Detroit-style pizza for game day"),
           dict(prompt_id="q057", prompt_text="What is Detroit-style pizza at Little Caesars?"),
           dict(prompt_id="q062", prompt_text="Best pizza for a Super Bowl party"),
           dict(prompt_id="q085", prompt_text="What are Crazy Puffs?")]

def test_item_prompt_ids_resolve_tracked_prompt_text_to_the_menu_item():
    assert item_prompt_ids("detroit_pepperoni", TRACKED, menu_items()) == ["q057", "q202"]
    assert item_prompt_ids("crazy_puffs_pepperoni", TRACKED, menu_items()) == ["q085"]
    assert item_prompt_ids("pretzel_crust", TRACKED, menu_items()) == []
    assert item_prompt_ids("detroit_pepperoni", TRACKED + [dict(prompt_id="s_x", prompt_text="Detroit-style deal")], menu_items()) \
        == ["q057", "q202"]   # suggestions never link this way

def test_q202_links_to_a_detroit_moment_with_no_semantic_match():
    m = {"item_id": "detroit_pepperoni"}
    q = "Where can I get the Goff pizza?"
    ids, new = link_moment(m, [q], lambda t, k=5: [], 0.80, TRACKED, menu_items())
    assert ids == [suggestion_id(q), "q057", "q202"] and new == [(suggestion_id(q), q)]
    hit = [{"id": "q202", "kind": "tracked", "score": 0.81}]
    assert link_moment(m, [q], lambda t, k=5: hit, 0.80, TRACKED, menu_items()) == (["q202", "q057"], [])   # deduped
