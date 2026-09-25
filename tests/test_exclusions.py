import pytest
from geologic.datagen.reference import exclusion_rules, personas
from geologic.exclusions import find_exclusion, assert_persona_invariant

RULES = exclusion_rules()

def test_persona_rule():
    assert find_exclusion("anything", "p_fictional_dax", [], RULES) == "EX-01"

def test_topic_rule_in_text_case_insensitive():
    assert find_exclusion("Fans react to ARREST report", None, [], RULES) == "EX-07"

def test_topic_rule_from_classified_topics():
    assert find_exclusion("clean text", None, ["gambling"], RULES) == "EX-03"

def test_no_match():
    assert find_exclusion("Crazy Puffs are great", "p_kittle", ["food"], RULES) is None

def test_real_endorser_with_excluded_topic_quarantines_but_person_stays_clean():
    # Review Focus 5
    rule = find_exclusion("Justin Jefferson asked about politics at presser", "p_jefferson", [], RULES)
    assert rule == "EX-02"
    assert_persona_invariant(personas())
    assert not next(p for p in personas() if p["persona_id"] == "p_jefferson")["is_excluded"]

def test_inactive_rule_ignored():
    rules = [dict(r, active=False) if r["rule_id"] == "EX-07" else r for r in RULES]
    assert find_exclusion("arrest", None, [], rules) is None

def test_invariant_raises():
    with pytest.raises(ValueError):
        assert_persona_invariant([{"persona_id": "x", "is_real": True, "is_excluded": True}])
