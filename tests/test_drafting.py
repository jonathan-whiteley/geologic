import json, pytest
from datetime import date
from geologic.datagen.reference import brand_facts, menu_items, exclusion_rules
from geologic.config import settings
from geologic.drafting import draft_messages, parse_draft, draft_fix, finalize_fix, unsupported_claims, DraftError

F = brand_facts(); T = date(2026, 10, 21)
REQ = {"fix_id": "fx_1", "issue_id": "is_1", "issue_type": "outdated", "issue_title": "partyplanner-weekly.com lists the Party Pack at an old price ($24.99)",
       "asset_type": "owned_patch", "lane": "counter_content", "page_id": "pg_deals_game_day", "section_id": "game-day-deals",
       "op": "insert", "section_before": "## Game Day Deals\n$4.99 online during NFL games.",
       "facts": [f for f in F if f["fact_id"] in ("F12", "F14", "F15")], "superseded": [f for f in F if f["fact_id"] == "F13"],
       "prompts": ["What should I order for a Super Bowl party for 12 people?"],
       "claim": {"text": "The Party Pack is $24.99.", "stated_value": "$24.99", "tag": "Outdated"},
       "passage": {"doc_id": "editorial_superbowl_roundup_2024", "domain": "partyplanner-weekly.com", "owner_class": "Editorial",
                   "last_updated": "2024-01-20", "url": "https://x", "excerpt": "Party Pack is $24.99 and feeds about 12."},
       "recipient": None, "persona_name": None, "persona_id": None, "prompt_ids": ["q201"]}
GOOD = {"patch": {"section_id": "game-day-deals", "op": "insert", "text": "## Feeding 12 for the big game\nThe Game Day Party Pack feeds 12 for $29.99."},
        "sentences": [{"text": "The Game Day Party Pack feeds 12 for $29.99.", "fact_ids": ["F12", "F14"]}], "rationale": "Answer first."}

class Chat:
    def __init__(self, *outs): self.outs, self.calls = list(outs), []
    def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
        self.calls.append(messages); return self.outs.pop(0)

def test_messages_carry_only_the_section_and_the_relevant_facts():
    m = draft_messages(REQ)
    user = m[1]["content"]
    assert "F12" in user and "F14" in user and "F13" in user and "do not use" in user
    assert "F03" not in user and REQ["section_before"] in user and "game-day-deals" in user
    assert "Never state a competitor" in m[0]["content"] and "\u2014" not in m[0]["content"] + user

def test_parse_draft_validates_shape_and_cleans_dashes():
    raw = json.dumps({**GOOD, "rationale": "Answer first \u2014 facts early."})
    assert parse_draft(f"```json\n{raw}\n```")["rationale"] == "Answer first, facts early."
    for bad in ("nope", json.dumps({"patch": {"op": "delete", "text": "x", "section_id": "a"}, "sentences": []}),
                json.dumps({"patch": {"op": "insert", "text": "", "section_id": "a"}, "sentences": []})):
        with pytest.raises(DraftError):
            parse_draft(bad)

def test_draft_fix_retries_once_then_raises():
    assert draft_fix(REQ, Chat("garbage", json.dumps(GOOD)), "ep")["patch"]["section_id"] == "game-day-deals"
    with pytest.raises(DraftError):
        draft_fix(REQ, Chat("garbage", "still garbage"), "ep")

def test_finalize_grounded_patch_is_t1_pending():
    f = finalize_fix(GOOD, REQ, F, exclusion_rules(), T, item_names=[m["name"] for m in menu_items()],
                     persona_names=["Jared Goff"], judge=lambda text, g: [])
    assert f["tier"] == "T1" and f["state"] == "pending_review" and f["grounding_fact_ids"] == ["F12", "F14"]
    assert all(c["ok"] for c in f["checks"])

def test_finalize_unsupported_claim_fails_and_exclusion_blocks():
    f = finalize_fix(GOOD, REQ, F, exclusion_rules(), T, item_names=[], persona_names=[], judge=lambda text, g: ["Open until 2am."])
    assert next(c for c in f["checks"] if c["key"] == "unsupported")["ok"] is False
    bet = {**GOOD, "patch": {**GOOD["patch"], "text": "## X\nParlay boost tonight. Gambling problem? Call 1-800-GAMBLER."}, "sentences": []}
    f = finalize_fix(bet, REQ, F, exclusion_rules(), T, item_names=[], persona_names=[], judge=lambda t, g: [])
    assert f["state"] == "blocked" and f["exclusion_rule_id"] == "EX-03"

def test_unsupported_claims_uses_the_judge_and_grounding():
    chat = Chat(json.dumps([{"text": "Feeds 12.", "subject": "party_pack", "attribute": "serves", "stated_value": "12"},
                            {"text": "Open until 2am.", "subject": "brand", "attribute": "other", "stated_value": "2am"}]))
    out = unsupported_claims("text", [f for f in F if f["fact_id"] in ("F12", "F14")], chat, "ep", ("party_pack", "brand"))
    assert out == ["Open until 2am."]

def test_model_calls_carry_the_v3_usage_context_and_unreadable_judge_fails_closed():
    seen = []
    class Ctx(Chat):
        def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
            seen.append(usage_context); return super().complete(endpoint, messages, max_tokens)
    draft_fix(REQ, Ctx(json.dumps(GOOD)), "ep")
    assert unsupported_claims("text", [], Ctx('{"not": "a list"}'), "ep", ("brand",)) == ["The judge could not read this draft"]
    assert [c["role"] for c in seen] == ["drafter", "draft_judge"] and {c["app"] for c in seen} == {settings.usage_app}
