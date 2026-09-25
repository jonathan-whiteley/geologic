"""Deterministic autonomy tiers. Agents never choose a tier."""
from __future__ import annotations

TIERS = ("T0", "T1", "T2", "BLOCKED")
_T0 = {"jsonld", "alt_text", "facts"}
_T1 = {"faq", "description"}
MIN_CONFIDENCE = 0.7

def assign_tier(asset_type: str, *, touches_persona: bool, visual_sourced: bool, exclusion_hit: bool,
                jsonld_valid: bool = True, resolution_confidence: float = 1.0) -> str:
    if exclusion_hit:
        return "BLOCKED"
    if touches_persona or visual_sourced:
        return "T2"
    if asset_type in _T0:
        if not jsonld_valid or resolution_confidence < MIN_CONFIDENCE:
            return "T1"
        return "T0"
    if asset_type in _T1:
        return "T1"
    return "T2"
