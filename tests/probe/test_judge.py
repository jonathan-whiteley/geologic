import pytest
from geologic.probe.judge import parse_judge_output, JudgeParseError

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
