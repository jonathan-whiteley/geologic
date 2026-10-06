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


def test_clean_removes_em_and_en_dashes():
    from geologic.agents.strategist import _clean
    em, en = "—", "–"
    assert _clean(f"Fast {em} and fresh") == "Fast, and fresh"
    assert _clean(f"3{en}4 adults") == "3-4 adults"
    assert _clean(f"wings{em}four flavors") == "wings, four flavors"
    out = _clean(f"a {en} b {em} c")
    assert em not in out and en not in out


def test_clean_leaves_no_stray_comma_punctuation():  # finding 11
    from geologic.agents.strategist import _clean
    em, en = "\u2014", "\u2013"
    assert _clean(f"Hot and ready {em}.") == "Hot and ready."
    assert _clean(f"Hot and ready {em} ") == "Hot and ready"
    assert _clean(f"Hot {em}, ready") == "Hot, ready"
    assert _clean(f"Line one {en}\n{em} line two") == "Line one\nline two"
    js = '{\n  "name": "Classic Pepperoni",\n  "price": "6.49"\n}'
    assert _clean(js) == js  # JSON-LD trailing commas untouched


def test_finalize_cleans_generated_text_but_not_diff_before():
    em = "—"
    draft = {"asset_type": "faq", "diff_before": f"old {em} body", "diff_after": f"New {em} text 3–4", "rationale": f"why {em} because"}
    f = finalize(draft, {"opp_id": "o", "title": f"T {em} x"}, exclusion_rules(), menu_items())
    assert f["diff_after"] == "New, text 3-4" and f["rationale"] == "why, because"
    assert f["diff_before"] == f"old {em} body" and f["title"] == "T, x"
