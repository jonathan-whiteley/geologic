import pytest
from geologic.datagen.reference import exclusion_rules, personas
from geologic.exclusions import find_exclusion, assert_persona_invariant

RULES = exclusion_rules()

REPOST = ("Corner piece energy before kickoff. Same-game parlay boost on Detroit tonight, odds in bio. "
          "Gambling problem? Call 1-800-GAMBLER.")

def test_sportsbook_repost_is_gambling():
    assert find_exclusion(REPOST, None, [], RULES) == "EX-03"
    assert "EX-01" not in {x["rule_id"] for x in RULES}

def test_topic_rule_in_text_case_insensitive():
    assert find_exclusion("Fans react to ARREST report", None, [], RULES) == "EX-07"

def test_topic_rule_from_classified_topics():
    assert find_exclusion("clean text", None, ["gambling"], RULES) == "EX-03"

def test_no_match():
    assert find_exclusion("Crazy Puffs are great", None, ["food"], RULES) is None

def test_excluded_topic_quarantines_and_no_person_is_excluded():
    # Never attach an exclusion story to a real person: topics quarantine, persona None.
    assert find_exclusion("Fans argue about politics at the presser", None, [], RULES) == "EX-02"
    assert_persona_invariant(personas())
    assert not any(p["is_excluded"] for p in personas())

def test_inactive_rule_ignored():
    rules = [dict(r, active=False) if r["rule_id"] == "EX-07" else r for r in RULES]
    assert find_exclusion("arrest", None, [], rules) is None

def test_invariant_raises():
    with pytest.raises(ValueError):
        assert_persona_invariant([{"persona_id": "x", "is_real": True, "is_excluded": True}])
