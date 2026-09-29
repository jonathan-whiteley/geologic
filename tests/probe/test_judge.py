import pytest
from geologic.probe.judge import parse_judge_output, normalize_brand, JudgeParseError

def test_fenced_json():
    r = parse_judge_output('```json\n{"lce_mentioned": true, "lce_rank": 1, "brands_mentioned": ["Little Caesars"], "sentiment": "positive", "claims": [{"item": "Hot-N-Ready", "price": "$5"}]}\n```')
    assert r.lce_mentioned and r.lce_rank == 1 and r.claims[0]["price"] == "$5"

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
