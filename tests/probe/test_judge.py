import pytest
from geologic.probe.judge import judge_messages, parse_judge_output, normalize_brand, JudgeParseError

def test_fenced_json():
    r = parse_judge_output('```json\n{"lce_mentioned": true, "lce_rank": 1, "brands_mentioned": ["Little Caesars"], "sentiment": "positive", "claims": [{"text": "It is $5.", "subject": "classic_pepperoni", "attribute": "price", "stated_value": "$5"}]}\n```', subjects=("classic_pepperoni",))
    assert r.lce_mentioned and r.lce_rank == 1 and r.claims[0]["stated_value"] == "$5"

def test_not_mentioned_rank_none():
    r = parse_judge_output('{"lce_mentioned": false, "lce_rank": 3, "brands_mentioned": [], "sentiment": "neutral", "claims": []}')
    assert r.lce_rank is None

@pytest.mark.parametrize("bad", ["", "not json", '{"lce_mentioned": "maybe"}', "[]"])
def test_malformed(bad):
    with pytest.raises(JudgeParseError):
        parse_judge_output(bad)

@pytest.mark.parametrize("variant,canonical", [
    ("Dominos", "Domino's"),
    ("dominos", "Domino's"),
    ("Papa John's", "Papa Johns"),
    ("papa john's", "Papa Johns"),
    ("Little Caesar's", "Little Caesars"),
    ("Pizza Hut", "Pizza Hut"),
    ("pizzahut", "Pizza Hut"),
    ("Unknown Brand", "Unknown Brand"),  # passthrough
])
def test_normalize_brand(variant, canonical):
    assert normalize_brand(variant) == canonical

def test_brands_mentioned_normalized_and_deduped():
    r = parse_judge_output('{"lce_mentioned": true, "lce_rank": 2, "brands_mentioned": ["Dominos", "Little Caesar\'s", "domino\'s"], "sentiment": "neutral", "claims": []}')
    # Dominos and domino's both map to Domino's; deduped to first occurrence
    assert r.brands_mentioned == ["Domino's", "Little Caesars"]


def test_judge_prompt_lists_vocabulary():
    m = judge_messages("q", "a", subjects=("party_pack", "brand"))
    assert "party_pack" in m[0]["content"] and "price" in m[0]["content"] and "stated_value" in m[0]["content"]

def test_parse_normalizes_claims():
    raw = ('{"lce_mentioned": true, "lce_rank": 2, "brands_mentioned": ["dominos", "Little Caesars"], "sentiment": "neutral",'
           ' "claims": [{"text": "Party Pack is $24.99.", "subject": "party_pack", "attribute": "price", "stated_value": "$24.99"},'
           ' {"text": "x", "subject": "pizza_mystery", "attribute": "vibes", "stated_value": 3}]}')
    j = parse_judge_output(raw, subjects=("party_pack",))
    assert j.brands_mentioned == ["Domino's", "Little Caesars"]
    assert j.claims == [{"text": "Party Pack is $24.99.", "subject": "party_pack", "attribute": "price", "stated_value": "$24.99"},
                        {"text": "x", "subject": "unknown", "attribute": "other", "stated_value": "3"}]

def test_parse_tolerates_missing_and_malformed_claim_fields():
    raw = ('{"lce_mentioned": true, "lce_rank": 1, "brands_mentioned": [], "sentiment": "neutral",'
           ' "claims": ["not a dict", {"subject": "brand", "attribute": "founded"}]}')
    assert parse_judge_output(raw, subjects=("brand",)).claims == [
        {"text": "", "subject": "brand", "attribute": "founded", "stated_value": None}]

def test_judge_prompt_strict_and_subject_list():
    m = judge_messages("q", "a", strict=True, subjects=("party_pack", "brand"))
    assert "SUBJECTS: party_pack, brand" in m[0]["content"] and "No markdown fences" in m[0]["content"]
    assert "{subjects}" not in m[0]["content"] and "{attributes}" not in m[0]["content"]
