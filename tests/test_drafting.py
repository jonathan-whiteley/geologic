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


# Fix round 1
from geologic.datagen.reference import personas, site_pages
from geologic.jsonld import build_for_page

NAMES = [m["name"] for m in menu_items()]
JREQ = {"asset_type": "jsonld", "section_id": "jsonld", "op": "replace", "persona_id": None, "persona_name": None}

def fin(d, req=REQ, judge=lambda t, g: [], persons=None):
    return finalize_fix(d, req, F, exclusion_rules(), T, item_names=NAMES,
                        persona_names=personas() if persons is None else persons, judge=judge)

def ok_of(f):
    return {c["key"]: c["ok"] for c in f["checks"]}

def test_surname_only_is_t2_and_fails_persona():
    s = "Goff picked the Game Day Party Pack for $29.99."
    f = fin({**GOOD, "patch": {**GOOD["patch"], "text": f"## X\n{s}"}, "sentences": [{"text": s, "fact_ids": ["F12"]}]})
    assert f["tier"] == "T2" and ok_of(f)["persona"] is False

def test_missing_or_failing_judge_fails_closed():
    for judge in (None, lambda t, g: 1 / 0):
        c = next(c for c in fin(GOOD, judge=judge)["checks"] if c["key"] == "unsupported")
        assert c == {"key": "unsupported", "ok": False, "label": "Unsupported-claim check did not run"}

def test_checks_come_back_in_ui_order():
    keys = [c["key"] for c in fin(GOOD)["checks"]]
    assert keys == ["grounded", "current", "values", "comparison", "persona", "copy", "target", "unsupported", "policy"]

def _built(page_id="pg_item_party_pack"):
    return build_for_page(next(p for p in site_pages() if p["page_id"] == page_id), F, T)

def test_built_jsonld_is_t0_with_every_check():
    for pid in ("pg_item_party_pack", "pg_deals_game_day"):
        f = fin(_built(pid), JREQ, judge=None)
        assert f["tier"] == "T0" and f["state"] == "pending_review", f["checks"]
        assert [c["key"] for c in f["checks"]] == ["grounded", "current", "values", "comparison", "persona", "copy", "target",
                                                   "policy", "schema"]

def test_jsonld_needs_a_current_cited_fact():
    f = fin({**_built(), "sentences": []}, JREQ)
    assert f["tier"] == "T1" and ok_of(f)["grounded"] is False
    d = _built()
    f = fin({**d, "sentences": [{**d["sentences"][0], "fact_ids": ["F13"]}]}, JREQ)
    assert f["tier"] == "T1" and ok_of(f)["current"] is False
    f = fin({**d, "sentences": [{**d["sentences"][0], "fact_ids": ["F99"]}]}, JREQ)
    assert ok_of(f)["current"] is False

def test_jsonld_free_text_person_and_competitor_never_t0():
    obj = json.loads(_built()["patch"]["text"])
    goff = {**_built(), "patch": {**_built()["patch"], "text": json.dumps({**obj, "description": "Goff loves it"})}}
    f = fin(goff, JREQ)
    assert f["tier"] == "T2" and ok_of(f)["persona"] is False and ok_of(f)["schema"] is False
    comp = {**_built(), "patch": {**_built()["patch"], "text": json.dumps({**obj, "name": "Better than Domino's"})}}
    f = fin(comp, JREQ)
    assert f["tier"] == "T1" and ok_of(f)["comparison"] is False

def test_jsonld_organization_offer_price_must_match_the_fact():
    d = _built("pg_deals_game_day")
    f = fin({**d, "patch": {**d["patch"], "text": d["patch"]["text"].replace('"4.99"', '"1.99"')}}, JREQ)
    assert f["tier"] == "T1" and ok_of(f)["values"] is False

def test_parse_draft_rejects_bad_types_and_unknown_asset():
    for bad in ({"patch": {"section_id": "a", "op": "insert", "text": ["x"]}, "sentences": []},
                {**GOOD, "sentences": [{"text": "x", "fact_ids": "F12"}]}):
        with pytest.raises(DraftError):
            parse_draft(json.dumps(bad))
    with pytest.raises(DraftError):
        draft_messages({**REQ, "asset_type": "mystery"})

def test_gridiron_copy_stays_t1_with_creator_personas():
    s = "Gridiron snacks for the big game."
    d = {**GOOD, "patch": {**GOOD["patch"], "text": GOOD["patch"]["text"] + " " + s}, "sentences": GOOD["sentences"]}
    f = fin(d, {**REQ, "asset_type": "answer_page"})
    assert f["tier"] == "T1" and all(c["ok"] for c in f["checks"]), f["checks"]
