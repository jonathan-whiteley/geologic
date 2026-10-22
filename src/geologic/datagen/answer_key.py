"""v3 planted stories: the issues, sources and fixes the build must surface (data only; the harness is Task 7)."""
ANSWER_KEY = {
    "party_pack": {"issue_type": "outdated", "subject": "party_pack", "attribute": "price",
                   "source_doc_id": "editorial_superbowl_roundup_2024", "stated_fact_id": "F13", "truth_fact_id": "F12",
                   "fixes": {"correction_email": "T2", "owned_patch": "T1"}},
    "gameday_listicle": {"issue_type": "missing_us", "source_doc_id": "review_pizzahut_gameday_top", "fixes": {"answer_page": "T1"}},
    "classic_pepperoni": {"issue_type": "outdated", "source_doc_id": "lce_pg_item_classic_pepperoni",
                          # one issue per stale page (S2-D): the owned patch and the T0 JSON-LD
                          "fixes": {"owned_patch": "T1", "jsonld": "T0"}},
    "reddit_price": {"issue_type": "wrong", "subject": "classic_pepperoni", "source_doc_id": "reddit_pizza_hnr",
                     "fixes": {"community_reply": "T2"}},
    "comparison_memory": {"issue_type": "no_answer_page", "cluster": "comparison", "fixes": {"answer_page": "T1"}},
    "goff_moment": {"issue_type": "moment_gap", "persona_id": "p_goff", "item_id": "detroit_pepperoni", "prompt_id": "q202",
                    "fixes": {"moment_page": "T1", "association": "T2"}},
    "sportsbook_repost": {"author": "@sidelinebets", "rule_id": "EX-03", "enforcement_points": ["ingest", "suggest", "publish"]},
}
TRACKED_COUNT = 30
ENGINE_COUNT = 4
