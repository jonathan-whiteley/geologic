from datetime import date, datetime
from geologic.datagen.reference import brand_facts, personas, site_pages
from geologic.fixes import fix_id, build_requests, relevant_facts, UPSERT_FIX, FIX_COLUMNS, fix_values

T, F = date(2026, 10, 21), brand_facts()
PAGES = {p["page_id"]: p for p in site_pages()}
SRC = [{"doc_id": "editorial_superbowl_roundup_2024", "domain": "partyplanner-weekly.com", "owner_class": "Editorial",
        "last_updated": date(2024, 1, 20), "url": "https://p", "body": "Little Caesars' Game Day Party Pack is $24.99 and feeds about 12."}]
PROMPTS = [{"prompt_id": "q201", "prompt_text": "What should I order for a Super Bowl party for 12 people?"}]
CLAIMS = [{"tag": "Outdated", "source_doc_id": "editorial_superbowl_roundup_2024", "subject": "party_pack", "attribute": "price",
           "text": "The Party Pack is $24.99.", "stated_value": "$24.99"}]
ISSUE = {"issue_id": "is_pp", "issue_type": "outdated", "title": "partyplanner-weekly.com lists the Game Day Party Pack at an old price ($24.99)",
         "rank": 1, "cluster": "game_day_party", "subject": "party_pack", "attribute": "price", "item_id": "party_pack",
         "source_doc_id": "editorial_superbowl_roundup_2024", "persona_id": None, "prompt_ids": ["q201"],
         "claim_keys": ["Outdated|editorial_superbowl_roundup_2024|party_pack|price"],
         "planned": [{"asset_type": "correction_email", "lane": "request_correction", "page_id": None, "section_id": "email", "op": "insert",
                      "recipient": "partyplanner-weekly.com"},
                     {"asset_type": "owned_patch", "lane": "counter_content", "page_id": "pg_deals_game_day", "section_id": None, "op": "insert",
                      "recipient": None}]}

def reqs(issue=ISSUE):
    return build_requests(issue, pages=PAGES, sources=SRC, facts=F, prompts=PROMPTS, claims=CLAIMS, personas=personas(), today=T)

def test_fix_ids_are_stable_and_epoch_free():
    assert fix_id("is_pp", "owned_patch") == fix_id("is_pp", "owned_patch") and fix_id("is_pp", "owned_patch").startswith("fx_")

def test_requests_carry_only_relevant_current_facts_and_the_superseded_one():
    cur, old = relevant_facts(ISSUE, F, T)
    assert {"F12", "F14", "F15", "F06"} <= {f["fact_id"] for f in cur} and "F13" not in {f["fact_id"] for f in cur}
    assert [f["fact_id"] for f in old] == ["F13"]
    assert "F03" not in {f["fact_id"] for f in cur}     # classic pepperoni is not relevant to this issue

def test_owned_patch_anchors_after_the_last_section_and_email_has_no_page():
    email, patch = reqs()
    assert email["asset_type"] == "correction_email" and email["page_id"] is None and email["section_before"] == ""
    assert email["recipient"] == "partyplanner-weekly.com" and email["claim"]["stated_value"] == "$24.99"
    assert patch["section_id"] == "game-day-deals" and patch["op"] == "insert"
    assert patch["section_before"].startswith("## Game Day Deals") and patch["prompts"] == [PROMPTS[0]["prompt_text"]]
    assert patch["passage"]["excerpt"].startswith("Little Caesars'") and patch["persona_name"] is None

def test_association_request_names_the_person_and_moment_page_does_not():
    moment = {**ISSUE, "issue_id": "is_m", "issue_type": "moment_gap", "subject": None, "attribute": None, "item_id": "detroit_pepperoni",
              "cluster": "game_day_party", "persona_id": "p_goff", "source_doc_id": None, "claim_keys": [],
              "planned": [{"asset_type": "moment_page", "lane": "capture_moment", "page_id": "pg_moment_detroit_pepperoni",
                           "section_id": "main", "op": "insert", "recipient": None},
                          {"asset_type": "association", "lane": "capture_moment", "page_id": "pg_moment_detroit_pepperoni",
                           "section_id": "association", "op": "insert", "recipient": None}]}
    page, assoc = reqs(moment)
    assert page["persona_name"] is None and assoc["persona_name"] == "Jared Goff" and page["section_before"] == ""
    assert "F08" in {f["fact_id"] for f in page["facts"]}

def test_upsert_sql_shape():
    assert UPSERT_FIX.count("%s") == len(FIX_COLUMNS) and "WHERE fixes.state IN ('pending_review', 'blocked')" in UPSERT_FIX
    final = {"patch": {"section_id": "s", "op": "insert", "text": "t"}, "sentences": [], "rationale": "r", "tier": "T1",
             "state": "pending_review", "checks": [{"key": "grounded", "ok": True, "label": "x"}], "grounding_fact_ids": [],
             "exclusion_rule_id": None}
    vals = fix_values(reqs()[1], final, 1, "tr")
    assert len(vals) == len(FIX_COLUMNS) and vals[FIX_COLUMNS.index("title")].startswith("Patch our page")
