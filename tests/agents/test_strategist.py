import json, pytest
from geologic.datagen.reference import menu_items, deals, exclusion_rules
from geologic.agents.strategist import draft_suggestion, finalize, DraftError

class Chat:
    def __init__(self, reply): self.reply = reply
    def complete(self, endpoint, messages, max_tokens=600): return self.reply

OPP = {"opp_id": "o1", "opp_type": "accuracy_fix", "item_id": "classic_pepperoni", "page_id": "pg_item_classic_pepperoni",
       "persona_id": None, "visual_sourced": False, "resolution_confidence": 0.95, "reasoning": "stale $5 price", "asset_type": "faq"}
PAGE = {"page_id": "pg_item_classic_pepperoni", "body": "## Classic Hot-N-Ready\nPepperoni pizza.", "jsonld": None}

def test_draft_parses_json():
    reply = json.dumps({"asset_type": "faq", "diff_after": "## Classic Hot-N-Ready\n### How much?\n$6.49.", "rationale": "adds price"})
    d = draft_suggestion(OPP, PAGE, menu_items(), deals(), Chat(reply), "ep")
    assert d["asset_type"] == "faq" and d["diff_before"] == PAGE["body"]

def test_draft_bad_output():
    with pytest.raises(DraftError):
        draft_suggestion(OPP, PAGE, menu_items(), deals(), Chat("sorry"), "ep")

def test_finalize_t1_and_checks():
    d = {"asset_type": "faq", "diff_before": "a", "diff_after": "A Classic Hot-N-Ready Pepperoni is $6.49.", "rationale": "r"}
    f = finalize(d, OPP, exclusion_rules(), menu_items())
    assert f["tier"] == "T1" and f["exclusion_rule_id"] is None
    assert any(c["label"].startswith("No exclusion") and c["ok"] for c in f["checks"])

def test_finalize_blocks_exclusion_in_draft_text():
    d = {"asset_type": "faq", "diff_before": "a", "diff_after": "Dax Merriwether arrest special", "rationale": "r"}
    f = finalize(d, {**OPP, "persona_id": "p_fictional_dax"}, exclusion_rules(), menu_items())
    assert f["tier"] == "BLOCKED" and f["exclusion_rule_id"] == "EX-01"

def test_finalize_invalid_jsonld_bumps_to_t1():
    d = {"asset_type": "jsonld", "diff_before": None, "diff_after": "{bad", "rationale": "r"}
    assert finalize(d, OPP, exclusion_rules(), menu_items())["tier"] == "T1"
