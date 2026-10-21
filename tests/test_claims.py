from datetime import date
from geologic.claims import tag_claim, source_for, claim_rows, answer_id, accuracy, split_sentences
from geologic.datagen.reference import brand_facts, categories
from geologic.probe.engine import Doc

T, F, CAT = date(2026, 10, 21), brand_facts(), categories()

def c(subject, attribute, value, text=""):
    return {"subject": subject, "attribute": attribute, "stated_value": value, "text": text}

def test_current_value_is_correct():
    assert tag_claim(c("party_pack", "price", "$29.99"), F, T, CAT) == ("Correct", "F12")

def test_superseded_value_is_outdated():
    assert tag_claim(c("party_pack", "price", "24.99"), F, T, CAT) == ("Outdated", "F13")
    assert tag_claim(c("classic_pepperoni", "price", "$5"), F, T, CAT) == ("Outdated", "F04")

def test_no_matching_row_is_wrong_and_points_at_the_truth():
    assert tag_claim(c("classic_pepperoni", "price", "$4.25"), F, T, CAT) == ("Wrong", "F03")

def test_deal_price_counts_for_pizza_only():
    assert tag_claim(c("classic_pepperoni", "price", "$4.99"), F, T, CAT) == ("Correct", "F06")
    assert tag_claim(c("crazy_bread", "price", "$4.99"), F, T, CAT)[0] == "Wrong"

def test_serves_and_founded():
    assert tag_claim(c("party_pack", "serves", "12 people"), F, T, CAT) == ("Correct", "F14")
    assert tag_claim(c("brand", "founded", "1959"), F, T, CAT) == ("Correct", "F01")

def test_unparseable_and_unknown_are_unverifiable():  # Review Focus 5
    assert tag_claim(c("classic_pepperoni", "price", "a few bucks"), F, T, CAT) == ("Unverifiable", None)
    assert tag_claim(c("unknown", "price", "$9.99"), F, T, CAT) == ("Unverifiable", None)
    assert tag_claim(c("detroit_pepperoni", "style", "square"), F, T, CAT) == ("Unverifiable", None)
    assert tag_claim(c("party_pack", "price", None), F, T, CAT) == ("Unverifiable", None)

def test_validity_window_edges():
    assert tag_claim(c("party_pack", "price", "24.99"), F, date(2025, 8, 31), CAT) == ("Correct", "F13")
    assert tag_claim(c("party_pack", "price", "24.99"), F, date(2025, 9, 1), CAT) == ("Outdated", "F13")

def test_source_prefers_the_citation_in_the_claim_sentence():
    docs = [Doc("comp_x", "t", "Domino's $7.99", False), Doc("editorial_superbowl_roundup_2024", "t", "Party Pack is $24.99", False)]
    ans = "For 12 people, the Party Pack is $24.99 [editorial_superbowl_roundup_2024]. Domino's is $7.99 [comp_x]."
    assert source_for(c("party_pack", "price", "$24.99"), ans, docs) == "editorial_superbowl_roundup_2024"

def test_source_falls_back_to_retrieved_body_then_model_memory():
    docs = [Doc("filler_012", "t", "nothing here", False), Doc("reddit_pizza_hnr", "t", "Hot-N-Ready is $4.25 now", False)]
    assert source_for(c("classic_pepperoni", "price", "4.25"), "It costs $4.25.", docs) == "reddit_pizza_hnr"
    assert source_for(c("classic_pepperoni", "price", "7.77"), "It costs $7.77.", docs) is None

def test_digits_inside_citations_are_not_values():
    docs = [Doc("filler_012", "t", "x", False)]
    assert source_for(c("party_pack", "serves", "12"), "Feeds a crowd [filler_012].", docs) is None

def test_split_keeps_menu_names_with_inner_punctuation_whole():
    s = "Try the Detroit-Style Deep!Deep! Dish Pepperoni for $11.99. It feeds a crowd!"
    assert split_sentences(s) == ["Try the Detroit-Style Deep!Deep! Dish Pepperoni for $11.99.", "It feeds a crowd!"]
    assert split_sentences("deep!deep! dish is $11.99 [x]. Yes.") == ["deep!deep! dish is $11.99 [x].", "Yes."]
    assert split_sentences("One. Two!", names=()) == ["One.", "Two!"]

def test_claim_rows_and_accuracy():
    aid = answer_id("run_1", "q201", "Meta AI")
    assert aid.startswith("a_") and len(aid) == 18 and aid == answer_id("run_1", "q201", "Meta AI")
    docs = [Doc("editorial_superbowl_roundup_2024", "t", "Party Pack is $24.99", False)]
    rows = claim_rows(aid, {"run_id": "run_1", "epoch": 1, "prompt_id": "q201", "engine": "Meta AI"},
                      [c("party_pack", "price", "$24.99", "The Party Pack is $24.99."), c("party_pack", "serves", "12")],
                      F, docs, "The Party Pack is $24.99 [editorial_superbowl_roundup_2024]. It feeds 12.", T, CAT)
    assert [(r["tag"], r["fact_id"], r["source_doc_id"]) for r in rows] == [
        ("Outdated", "F13", "editorial_superbowl_roundup_2024"), ("Correct", "F14", None)]
    assert len({r["claim_id"] for r in rows}) == 2 and accuracy(rows) == 0.5 and accuracy([]) is None

def test_a_dollar_off_by_one_cent_is_not_the_same_value():
    assert tag_claim(c("crazy_bread", "price", "$4.00"), F, T, CAT) == ("Wrong", "F10")
    assert source_for(c("classic_pepperoni", "price", "$5"), "It is $5.", [Doc("d", "t", "Deal: $4.99", False)]) is None


def _fid(subject, attribute):
    return next(f["fact_id"] for f in F if f["subject"] == subject and f["attribute"] == attribute)


def test_founded_prefers_the_four_digit_year():
    assert tag_claim(c("brand", "founded", "May 8, 1959"), F, T, CAT) == ("Correct", "F01")
    assert tag_claim(c("brand", "founded", 1959), F, T, CAT) == ("Correct", "F01")
    assert tag_claim(c("brand", "founded", "May 8, 1962"), F, T, CAT) == ("Wrong", "F01")
    assert tag_claim(c("brand", "founded", "in 1962"), F, T, CAT) == ("Wrong", "F01")


def test_serves_range_matches_when_the_fact_is_inside():
    assert tag_claim(c("party_pack", "serves", "10-12 people"), F, T, CAT) == ("Correct", "F14")
    assert tag_claim(c("party_pack", "serves", "10 to 14"), F, T, CAT) == ("Correct", "F14")
    assert tag_claim(c("party_pack", "serves", "4-6 people"), F, T, CAT) == ("Wrong", "F14")
    assert tag_claim(c("party_pack", "serves", "8"), F, T, CAT) == ("Wrong", "F14")


def test_price_is_not_read_as_a_range():
    assert tag_claim(c("classic_pepperoni", "price", "$5-$7"), F, T, CAT) == ("Outdated", "F04")


def test_discontinued_item_skips_the_deal_price():
    gone, old = _fid("pretzel_crust", "available"), _fid("pretzel_crust", "price")
    assert tag_claim(c("pretzel_crust", "price", "$4.99"), F, T, CAT) == ("Wrong", gone)
    assert tag_claim(c("pretzel_crust", "price", "$8.99"), F, T, CAT) == ("Outdated", old)
    assert tag_claim(c("calzony", "price", "$4.99"), F, T, CAT) == ("Wrong", _fid("calzony", "available"))
    # before it was discontinued the deal still applied
    assert tag_claim(c("pretzel_crust", "price", "$4.99"), F, date(2025, 10, 1), CAT) == ("Correct", "F06")


def test_source_for_founded_and_serves_use_the_same_reading():
    docs = [Doc("lce_pg_about", "t", "Founded in 1959 in Garden City", True)]
    assert source_for(c("brand", "founded", "May 8, 1959"), "Little Caesars began in 1959.", docs) == "lce_pg_about"
    assert source_for(c("party_pack", "serves", "10-12"), "It feeds 10-12 [d1].", [Doc("d1", "t", "x", False)]) == "d1"
