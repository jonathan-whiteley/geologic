from geologic.drafting import plan_drafts, initial_state, suggestion_id, red_team_items

OPPS = [{"opp_id": "a", "rank": 2, "status": "open", "assets": ["jsonld", "faq"]},
        {"opp_id": "b", "rank": 1, "status": "open", "assets": ["faq"]},
        {"opp_id": "c", "rank": 3, "status": "monitor", "assets": ["description"]}]

def test_plan_drafts_rank_order_and_skips_monitor():
    items = plan_drafts(OPPS)
    assert [(i["opp_id"], i["asset_type"]) for i in items] == [("b", "faq"), ("a", "jsonld"), ("a", "faq")]

def test_initial_state():
    assert [initial_state(t) for t in ("T0", "T1", "T2", "BLOCKED")] == ["auto_published", "pending_review", "pending_review", "blocked"]

def test_suggestion_id_deterministic():
    assert suggestion_id("a", "faq", 1) == suggestion_id("a", "faq", 1) != suggestion_id("a", "faq", 2)

def test_red_team_items():
    items = red_team_items([{"signal_id": "x", "persona_id": "p_fictional_dax", "menu_item_id": "classic_pepperoni", "text": "Dax arrest"},
                            {"signal_id": "y", "persona_id": None, "menu_item_id": None, "text": "politics"}])
    assert len(items) == 2 and items[0]["forced_text"] == "Dax arrest" and items[0]["persona_id"] == "p_fictional_dax"
    assert items[0]["page_id"] == "pg_item_classic_pepperoni" and items[1]["page_id"] == "pg_about"

def test_upsert_updates_all_columns_and_guards_terminal_states():
    from geologic.drafting import UPSERT_SUGGESTION as U
    for col in ("rationale", "title", "diff_before", "exclusion_rule_id", "agent_trace_id", "page_id"):
        assert f"{col} = EXCLUDED.{col}" in U
    assert "WHERE suggestions.state IN ('drafted', 'pending_review', 'blocked')" in U
    assert U.count("%s") == 17


def test_redraft_clears_current_epoch_queue_only():
    from geologic.drafting import CLEAR_EPOCH_SUGGESTIONS, LIVE_SUGGESTION_IDS
    assert CLEAR_EPOCH_SUGGESTIONS.startswith("DELETE FROM suggestions WHERE epoch = %s")
    assert "cms_page_versions" not in CLEAR_EPOCH_SUGGESTIONS
    assert "auto_published" in LIVE_SUGGESTION_IDS and "DELETE" not in LIVE_SUGGESTION_IDS
