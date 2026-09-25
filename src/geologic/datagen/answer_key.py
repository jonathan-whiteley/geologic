"""Expected outcomes asserted by jobs/answer_key_check.py (Task 20)."""
ANSWER_KEY = {
    "S1": {"opp_type": "accuracy_fix", "page_id": "pg_item_classic_pepperoni", "tiers": ["T0", "T1"], "cluster": "value", "improves_after_publish": "accuracy"},
    "S2": {"opp_type": "content_gap", "page_id": "pg_deals_game_day", "tiers": ["T1"], "cluster": "game_day_party", "improves_after_publish": "answer_share"},
    "S3": {"opp_type": "persona_moment", "persona_id": "p_kittle", "item_id": "detroit_pepperoni", "tiers": ["T2"]},
    "S4": {"quarantined": True, "rule_id": "EX-01", "enforcement_points": ["ingest", "suggest", "publish"], "in_feed": False},
    "S5": {"higher_item": "crazy_puffs_pepperoni", "lower_item": "pretzel_crust"},
    "S6": {"opp_type": "content_gap", "cluster": "sponsorship", "tiers": ["T0", "T1"]},
    "S7": {"opp_type": "crawler_gap", "page_id": "pg_order", "tiers": ["T0"]},
}
