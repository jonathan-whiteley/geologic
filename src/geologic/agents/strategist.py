"""Content Strategist: drafts one content change for one opportunity. Tier and safety are decided in finalize()."""
from __future__ import annotations
import json
import re
from geologic.exclusions import find_exclusion
from geologic.facts import parse_price, resolve_item
from geologic.jsonld import validate
from geologic.tiering import assign_tier

class DraftError(ValueError):
    pass

ASSET_TYPES = {"jsonld", "faq", "description", "alt_text"}

SYSTEM = ("You are the Content Strategist for Little Caesars. Draft one change to one web page so AI answer engines "
          "can quote accurate, current facts. Use only the menu facts provided. Voice: friendly, plain, short sentences. "
          "Never mention competitors. Return only JSON: {\"asset_type\": one of jsonld|faq|description|alt_text, "
          "\"diff_after\": the full new page body (or full JSON-LD string for jsonld), \"rationale\": one sentence}.")

def _facts(menu, deals):
    lines = [f"- {m['name']}: ${m['price']:.2f}{'' if m['available'] else ' (discontinued)'}" for m in menu]
    lines += [f"- Deal: {d['name']} ${d['price']:.2f} ({d['channel']})" for d in deals if d["active"]]
    return "\n".join(lines)

def draft_suggestion(opp, page, menu, deals, chat, endpoint) -> dict:
    target = page["jsonld"] if opp.get("asset_type") == "jsonld" else page["body"]
    msg = (f"Opportunity: {opp['opp_type']} ({opp.get('reasoning', '')}).\nPreferred asset type: {opp.get('asset_type')}\n"
           f"Current page ({page['page_id']}):\n{target}\n\nMenu facts:\n{_facts(menu, deals)}")
    raw = chat.complete(endpoint, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": msg}], max_tokens=900)
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (raw or "").strip(), flags=re.MULTILINE)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise DraftError(f"not JSON: {raw[:80]}") from e
    if obj.get("asset_type") not in ASSET_TYPES or not obj.get("diff_after"):
        raise DraftError("missing asset_type or diff_after")
    before = page["jsonld"] if obj["asset_type"] == "jsonld" else page["body"]
    return {"asset_type": obj["asset_type"], "diff_before": before, "diff_after": obj["diff_after"],
            "rationale": obj.get("rationale", "")}

_PRICE_IN_TEXT = re.compile(r"\$\s?\d+(?:\.\d{2})?")

def finalize(draft, opp, rules, menu) -> dict:
    rule_id = find_exclusion(draft["diff_after"], opp.get("persona_id"), [], rules)
    checks = [{"ok": rule_id is None, "label": "No exclusion rule touched" if rule_id is None else f"Blocked by {rule_id}"}]
    jsonld_ok = True
    if draft["asset_type"] == "jsonld":
        errs = validate(draft["diff_after"], menu)
        jsonld_ok = not errs
        checks.append({"ok": jsonld_ok, "label": "schema.org validation passed" if jsonld_ok else "; ".join(errs)})
    else:
        item = resolve_item(opp.get("item_id") or "", menu) or next((m for m in menu if m["item_id"] == opp.get("item_id")), None)
        prices = [parse_price(p) for p in _PRICE_IN_TEXT.findall(draft["diff_after"])]
        allowed = {round(m["price"], 2) for m in menu} | {4.99}
        facts_ok = all(p in allowed for p in prices if p is not None)
        checks.append({"ok": facts_ok, "label": "Facts match the menu" if facts_ok else "A price does not match the menu"})
        if item is None and opp.get("item_id"):
            checks.append({"ok": False, "label": "Item not found on the menu"})
    tier = assign_tier(draft["asset_type"], touches_persona=bool(opp.get("persona_id")),
                       visual_sourced=bool(opp.get("visual_sourced")), exclusion_hit=rule_id is not None,
                       jsonld_valid=jsonld_ok, resolution_confidence=opp.get("resolution_confidence", 1.0))
    if tier in ("T1", "T2"):
        checks.append({"ok": False, "label": f"Needs your approval ({tier})"})
    return {**draft, "tier": tier, "exclusion_rule_id": rule_id, "checks": checks}
