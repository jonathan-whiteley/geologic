"""Plans which suggestions to draft and their initial workflow state."""
from __future__ import annotations
import hashlib

_STATE = {"T0": "auto_published", "T1": "pending_review", "T2": "pending_review", "BLOCKED": "blocked"}

def plan_drafts(opps):
    out = []
    for o in sorted((o for o in opps if o["status"] == "open"), key=lambda o: o["rank"]):
        for a in o["assets"]:
            out.append({**o, "asset_type": a})
    return out

def initial_state(tier: str) -> str:
    return _STATE[tier]

def suggestion_id(opp_id: str, asset_type: str, epoch: int) -> str:
    return "sg_" + hashlib.sha1(f"{opp_id}|{asset_type}|{epoch}".encode()).hexdigest()[:12]

def red_team_items(quarantined_signals):
    return [{"opp_id": f"redteam_{s['signal_id']}", "opp_type": "red_team", "rank": 999, "item_id": s.get("menu_item_id"),
             "page_id": f"pg_item_{s['menu_item_id']}" if s.get("menu_item_id") else "pg_about",
             "persona_id": s.get("persona_id"), "visual_sourced": False, "resolution_confidence": 1.0,
             "asset_type": "description", "forced_text": s["text"], "prompt_ids": [], "title": "Red-team check on quarantined signal"}
            for s in quarantined_signals]

# A full re-draft replaces the queue for the current epoch. Reset restores epoch-1 rows under the current epoch with their
# epoch-1 ids, while drafting hashes the current epoch into new ids, so without this the old and new rows would sit side by side.
# cms_page_versions is page history, not queue state, so it is left alone.
CLEAR_EPOCH_SUGGESTIONS = "DELETE FROM suggestions WHERE epoch = %s"
LIVE_SUGGESTION_IDS = "SELECT suggestion_id FROM suggestions WHERE state IN ('auto_published', 'published')"

UPSERT_SUGGESTION = """INSERT INTO suggestions (suggestion_id, epoch, opp_id, opp_rank, title, asset_type, page_id, diff_before, diff_after,
    rationale, tier, state, checks, exclusion_rule_id, persona_id, prompt_ids, agent_trace_id)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (suggestion_id) DO UPDATE SET opp_rank = EXCLUDED.opp_rank, title = EXCLUDED.title, asset_type = EXCLUDED.asset_type,
    page_id = EXCLUDED.page_id, diff_before = EXCLUDED.diff_before, diff_after = EXCLUDED.diff_after, rationale = EXCLUDED.rationale,
    tier = EXCLUDED.tier, state = EXCLUDED.state, checks = EXCLUDED.checks, exclusion_rule_id = EXCLUDED.exclusion_rule_id,
    persona_id = EXCLUDED.persona_id, prompt_ids = EXCLUDED.prompt_ids, agent_trace_id = EXCLUDED.agent_trace_id
    WHERE suggestions.state IN ('drafted', 'pending_review', 'blocked')"""
