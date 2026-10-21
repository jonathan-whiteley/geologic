from datetime import date
from geologic.datagen.reference import brand_facts, menu_items
from geologic.verify import verify, patch_sentences, supported, reground

T, F = date(2026, 10, 21), brand_facts()
NAMES = [m["name"] for m in menu_items()]
REQ = {"asset_type": "owned_patch", "section_id": "game-day-deals", "op": "insert"}

def draft(text, sentences, section="game-day-deals", op="insert"):
    return {"patch": {"section_id": section, "op": op, "text": text}, "sentences": sentences, "rationale": "r"}

def checks(d, req=REQ, persons=("Jared Goff",)):
    cs, sents = verify(d, req, F, T, item_names=NAMES, persona_names=persons)
    return {c["key"]: c["ok"] for c in cs}, sents

def test_grounded_patch_passes():
    d = draft("## Feeding 12 for the big game\nThe Game Day Party Pack feeds 12 for $29.99. Order ahead in the app.",
              [{"text": "The Game Day Party Pack feeds 12 for $29.99.", "fact_ids": ["F12", "F14"]},
               {"text": "Order ahead in the app.", "fact_ids": []}])
    ok, sents = checks(d)
    assert all(ok.values()), ok
    assert [s["kind"] for s in sents] == ["fact", "copy"]

def test_factual_sentence_without_fact_fails_grounded():
    ok, _ = checks(draft("## X\nThe Party Pack is $29.99.", [{"text": "The Party Pack is $29.99.", "fact_ids": []}]))
    assert ok["grounded"] is False

def test_superseded_fact_fails_current_and_wrong_number_fails_values():
    ok, _ = checks(draft("## X\nThe Party Pack is $24.99.", [{"text": "The Party Pack is $24.99.", "fact_ids": ["F13"]}]))
    assert ok["current"] is False
    ok, _ = checks(draft("## X\nThe Party Pack is $27.99.", [{"text": "The Party Pack is $27.99.", "fact_ids": ["F12"]}]))
    assert ok["values"] is False

def test_competitor_price_fails_comparison():
    s = "Domino's charges $7.99 but the Party Pack is $29.99."
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F12"]}]))
    assert ok["comparison"] is False

def test_person_named_outside_association_fails_and_is_allowed_in_association():
    s = "Jared Goff picked the Detroit-Style Deep!Deep! Dish Pepperoni."
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F09"]}]))
    assert ok["persona"] is False
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F09"]}], section="association"),
                   {"asset_type": "association", "section_id": "association", "op": "insert"})
    assert ok["persona"] is True

def test_copy_not_allowed_for_t0_assets_and_target_must_match():
    ok, _ = checks(draft("## X\nGreat for game day.", [{"text": "Great for game day.", "fact_ids": []}]),
                   {"asset_type": "jsonld", "section_id": "game-day-deals", "op": "insert"})
    assert ok["copy"] is False
    ok, _ = checks(draft("## X\nGreat for game day.", [], section="other", op="replace"))
    assert ok["target"] is False

def test_patch_sentences_skip_headings_and_keep_subject_line():
    assert patch_sentences("Subject: Party Pack price\n\n## H\nOne. Two!\n- Three?") == ["Subject: Party Pack price", "One.", "Two!", "Three?"]

def test_menu_name_with_inner_punctuation_stays_one_grounded_sentence():
    s = "The Detroit-Style Deep!Deep! Dish Pepperoni is $11.99."
    ok, sents = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F08"]}]))
    assert [x["text"] for x in sents] == [s] and ok["grounded"] and ok["values"]

def test_reground_keeps_unchanged_and_rederives_edited_sentences():
    prev = [{"text": "The Game Day Party Pack feeds 12 for $29.99.", "fact_ids": ["F12", "F14"]}]
    text = "## H\nThe Game Day Party Pack feeds 12 for $29.99. The Game Day Party Pack is $29.99 today. Grab one for the game."
    s = reground(text, prev, F, T, prior_ids=["F12", "F14"])
    assert [x["fact_ids"] for x in s] == [["F12", "F14"], ["F12"], []]
    ok, sents = checks(draft(text, s))
    assert ok["grounded"] and ok["copy"] and [x["kind"] for x in sents] == ["fact", "fact", "copy"]
    ok, _ = checks(draft(text, s), {"asset_type": "jsonld", "section_id": "game-day-deals", "op": "insert"})
    assert ok["copy"] is False                                    # copy, no facts is rejected for T0 assets
    assert reground("## H\nNow $27.99.", [], F, T)[0]["fact_ids"] == []   # no fact states 27.99: stays copy

def test_supported_by_any_grounding_value():
    g = [f for f in F if f["fact_id"] in ("F12", "F14")]
    assert supported({"subject": "party_pack", "stated_value": "$29.99"}, g)
    assert supported({"subject": "party_pack", "stated_value": "12 people"}, g)
    assert not supported({"subject": "party_pack", "stated_value": "open until 2am"}, g)
    assert supported({"subject": "party_pack", "stated_value": ""}, g)
