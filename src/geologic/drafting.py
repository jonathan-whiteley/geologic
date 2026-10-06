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
