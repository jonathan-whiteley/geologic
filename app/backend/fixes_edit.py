"""Human edit of a pending fix (spec 5.4): re-ground the sentences in code, then re-run every check."""
from geologic.drafting import finalize_fix
from geologic.verify import reground


def edit_fix(fix, patch_text, *, facts, rules, today, item_names, persona_names, judge):
    sentences = reground(patch_text, fix.get("sentences"), facts, today, prior_ids=fix.get("grounding_fact_ids") or ())
    draft = {"patch": {"section_id": fix["section_id"], "op": fix["op"], "text": patch_text}, "sentences": sentences,
             "rationale": fix.get("rationale") or ""}
    req = {k: fix.get(k) for k in ("asset_type", "section_id", "op", "persona_id")}
    return finalize_fix(draft, req, facts, rules, today, item_names=item_names, persona_names=persona_names,
                        judge=None if fix["asset_type"] == "jsonld" else judge)
