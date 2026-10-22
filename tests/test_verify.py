from datetime import date
from geologic.datagen.reference import brand_facts, menu_items, personas
from geologic.verify import (verify, patch_sentences, supported, reground, person_terms, is_factual,
                             _numbers)

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
    assert [s["kind"] for s in sents] == ["heading", "fact", "copy"]
    assert sents[0]["fact_ids"] == ["F12", "F14"]          # a heading inherits the facts cited in its section

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
                   {"asset_type": "association", "section_id": "association", "op": "insert",
                    "persona_id": "p_goff", "persona_name": "Jared Goff"})
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
    assert [x["text"] for x in sents if x["kind"] != "heading"] == [s] and ok["grounded"] and ok["values"]

def test_reground_keeps_unchanged_and_rederives_edited_sentences():
    prev = [{"text": "The Game Day Party Pack feeds 12 for $29.99.", "fact_ids": ["F12", "F14"]}]
    text = "## H\nThe Game Day Party Pack feeds 12 for $29.99. The Game Day Party Pack is $29.99 today. Grab one for the game."
    s = reground(text, prev, F, T, prior_ids=["F12", "F14"])
    assert [x["fact_ids"] for x in s] == [["F12", "F14"], ["F12"], []]
    ok, sents = checks(draft(text, s))
    assert ok["grounded"] and ok["copy"] and [x["kind"] for x in sents] == ["heading", "fact", "fact", "copy"]
    ok, _ = checks(draft(text, s), {"asset_type": "jsonld", "section_id": "game-day-deals", "op": "insert"})
    assert ok["copy"] is False                                    # copy, no facts is rejected for T0 assets
    assert reground("## H\nNow $27.99.", [], F, T)[0]["fact_ids"] == []   # no fact states 27.99: stays copy

def test_supported_by_any_grounding_value():
    g = [f for f in F if f["fact_id"] in ("F12", "F14")]
    assert supported({"subject": "party_pack", "attribute": "price", "stated_value": "$29.99"}, g)
    assert supported({"subject": "party_pack", "attribute": "serves", "stated_value": "12 people"}, g)
    assert not supported({"subject": "party_pack", "attribute": "other", "stated_value": "open until 2am"}, g)
    assert supported({"subject": "party_pack", "stated_value": ""}, g)


# Fix round 1
PEOPLE = personas()
GOFF_ASSOC = {"asset_type": "association", "section_id": "association", "op": "insert", "persona_id": "p_goff", "persona_name": "Jared Goff"}

def test_person_terms_cover_name_tokens_and_handles():
    terms = {t.lower() for t in person_terms([{"display_name": "Jared Goff", "handle": "@JaredGoff16"}, "Al Bo"])}
    assert {"jared goff", "jared", "goff", "jaredgoff", "@jaredgoff", "jaredgoff16", "@jaredgoff16", "al bo"} <= terms
    assert "al" not in terms and "bo" not in terms                     # tokens shorter than 3 are not terms

def test_persona_surname_possessive_lowercase_and_handle_fail_outside_association():
    for s in ("Goff picked the Game Day Party Pack for $29.99.", "Goff's pick is the Game Day Party Pack for $29.99.",
              "goff picked the Game Day Party Pack for $29.99.", "@jaredgoff picked the Game Day Party Pack for $29.99."):
        ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F12"]}]))
        assert ok["persona"] is False, s
    s = "Goffman picked the Game Day Party Pack for $29.99."
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F12"]}]))
    assert ok["persona"] is True

def test_a_person_name_makes_a_sentence_factual_on_word_boundaries():
    terms = person_terms(["Jared Goff"])
    assert is_factual("Goff loves it.", terms) and not is_factual("Goffman loves it.", terms)
    ok, _ = checks(draft("## X\nGoff loves it.", [{"text": "Goff loves it.", "fact_ids": []}]))
    assert ok["grounded"] is False

def test_association_exempts_only_the_planned_persona():
    s = "Jared Goff and SliceQueen picked the Detroit-Style Deep!Deep! Dish Pepperoni."
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F09"]}], section="association"), GOFF_ASSOC, PEOPLE)
    assert ok["persona"] is False
    s = "Jared Goff picked the Detroit-Style Deep!Deep! Dish Pepperoni."
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F09"]}], section="association"), GOFF_ASSOC, PEOPLE)
    assert ok["persona"] is True
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F09"]}], section="association"),
                   {**GOFF_ASSOC, "persona_id": "p_creator_slicequeen", "persona_name": "SliceQueen"}, PEOPLE)
    assert ok["persona"] is False                                   # Goff is not the planned persona here

def test_headings_are_verified_like_sentences():
    body = "The Game Day Party Pack feeds 12 for $29.99."
    ok, sents = checks(draft(f"## Party Pack now $19.99 per Goff\n{body}", [{"text": body, "fact_ids": ["F12", "F14"]}]))
    assert sents[0]["kind"] == "heading" and ok["values"] is False and ok["persona"] is False
    ok, _ = checks(draft("## Party Pack for $29.99\nGreat for game day.", [{"text": "Great for game day.", "fact_ids": []}]))
    assert ok["grounded"] is False                                  # a factual heading over an uncited section
    ok, _ = checks(draft("## Domino's is $7.99\nGreat for game day.", [{"text": "Great for game day.", "fact_ids": []}]))
    assert ok["comparison"] is False

def test_competitor_names_fold_apostrophes():
    for s in ("Domino\u2019s charges $7.99 for one.", "dominos charges $7.99 for one.", "Papa John\u2019s charges $7.99 for one."):
        ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": ["F18"]}]))
        assert ok["comparison"] is False, s

def test_numbers_keep_comma_lists_apart():
    assert _numbers("feeds 12,15 people") == [12.0, 15.0]
    assert _numbers("1,600,000 fans and $1,299.99") == [1600000.0, 1299.99]

def test_supported_needs_the_attribute_and_subject_and_token_boundaries():
    g = [f for f in F if f["fact_id"] in ("F12", "F14", "F15")]
    assert not supported({"subject": "party_pack", "attribute": "other", "stated_value": "open until 12am"}, g)
    assert not supported({"subject": "party_pack", "attribute": "serves", "stated_value": "open until 12am"}, g)
    assert not supported({"subject": "brand", "attribute": "serves", "stated_value": "12"}, g)
    assert supported({"attribute": "serves", "stated_value": "12"}, g)
    assert supported({"subject": "party_pack", "attribute": "contents", "stated_value": "3 large pizzas"}, g)
    assert not supported({"subject": "party_pack", "attribute": "contents", "stated_value": "3 orders of Crazy Bread"}, g)
    assert not supported({"subject": "party_pack", "attribute": "contents", "stated_value": "large pizza"}, g)
    assert not supported({"subject": "party_pack", "attribute": "contents",
                          "stated_value": "3 large pizzas and 2 orders of Crazy Bread plus free wings"}, g)   # no reverse containment

def test_empty_stated_value_is_supported_only_when_not_factual():
    g = [f for f in F if f["fact_id"] in ("F12", "F14")]
    assert not supported({"text": "Feeds 12.", "attribute": "serves", "stated_value": ""}, g)
    assert not supported({"text": "Goff loves it.", "attribute": "other", "stated_value": None}, g, person_terms(["Jared Goff"]))
    assert supported({"text": "Great for game day.", "attribute": "other", "stated_value": ""}, g)

# Fix round 2: single name tokens only for real people; creators match on full name or handle
def test_creator_tokens_do_not_trip_persona_but_full_name_and_handle_do():
    s = "Gridiron snacks for the big game."
    ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": []}]), REQ, PEOPLE)
    assert ok["persona"] is True and ok["grounded"] is True
    for s in ("Gridiron Grub loves the big game.", "@gridirongrub loves the big game.", "gridirongrub loves the big game."):
        ok, _ = checks(draft(f"## X\n{s}", [{"text": s, "fact_ids": []}]), REQ, PEOPLE)
        assert ok["persona"] is False, s
    ok, _ = checks(draft("## X\nGoff loves the big game.", [{"text": "Goff loves the big game.", "fact_ids": []}]), REQ, PEOPLE)
    assert ok["persona"] is False
    rows = {t.lower() for t in person_terms(PEOPLE)}
    assert "goff" in rows and "jared" in rows and "gridiron" not in rows and "grub" not in rows
    assert "grub" in {t.lower() for t in person_terms(["Gridiron Grub"])}     # plain strings stay conservative


# Task 15 (live drafts): descriptive facts are matched on their words, not on the judge's exact paraphrase
def test_supported_descriptive_facts_by_word_coverage_but_not_counted_or_tagged_ones():
    g = [f for f in F if f["fact_id"] in ("F02", "F05", "F09", "F11", "F12", "F14", "F15")]
    assert supported({"subject": "party_pack", "attribute": "ordering", "stated_value": "Pizza Portal pickup available to order ahead"}, g)
    assert supported({"subject": "detroit_pepperoni", "attribute": "contents", "stated_value": "crispy cheese edges"}, g)
    assert supported({"subject": "classic_pepperoni", "attribute": "ordering", "stated_value": "Ready when you walk in, no waiting"}, g)
    assert supported({"subject": "brand", "attribute": "nfl_sponsor", "stated_value": "Official Pizza Sponsor of the NFL since 2023"}, g)
    assert not supported({"subject": "brand", "attribute": "nfl_sponsor", "stated_value": "Official Pizza Sponsor of the NFL since 2019"}, g)
    assert not supported({"subject": "brand", "attribute": "other", "stated_value": "free delivery on every order"}, g)
    # counted and tagged facts keep exact matching (the earlier pins)
    assert not supported({"subject": "party_pack", "attribute": "contents", "stated_value": "3 orders of Crazy Bread"}, g)
    assert not supported({"subject": "party_pack", "attribute": "contents", "stated_value": "large pizza"}, g)
    assert not supported({"subject": "party_pack", "attribute": "price", "stated_value": "$59.98"}, g)
