"""Deterministic autonomy tiers (spec 5.2). Code assigns tiers from asset type, person present and check results; the
LLM never does. BLOCKED is a state, not a tier."""
TIERS = ("T0", "T1", "T2")
T0_ASSETS = {"jsonld"}
T1_ASSETS = {"owned_patch", "answer_page", "moment_page"}
T2_ASSETS = {"association", "correction_email", "community_reply"}


def assign_tier(asset_type: str, *, names_person: bool, checks_ok: bool) -> str:
    if names_person or asset_type in T2_ASSETS:
        return "T2"
    if asset_type in T0_ASSETS:
        return "T0" if checks_ok else "T1"
    if asset_type in T1_ASSETS:
        return "T1"
    return "T2"
