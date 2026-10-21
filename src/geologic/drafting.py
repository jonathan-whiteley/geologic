"""Grounded drafter v2 (spec 5.4): structured section patches grounded in brand_facts, then verified by code."""
from __future__ import annotations
import json
import re
from geologic.exclusions import find_exclusion
from geologic.jsonld import validate_against_facts
from geologic.probe.engine import usage_context
from geologic.probe.judge import ATTRIBUTES_TEXT
from geologic.style import clean_dashes
from geologic.tiering import assign_tier
from geologic.verify import supported, verify

BLOCKING_CHECKS = {"grounded", "current", "values", "comparison", "persona", "copy", "target", "unsupported", "policy", "schema"}


class DraftError(ValueError):
    pass


SYSTEM = ("You are the Content Strategist for Little Caesars. You write one small change that is grounded in facts. "
          "Use only the facts provided, quote their values exactly, and list the fact ids behind every sentence. "
          "Never state a competitor's price; compare only on Little Caesars facts. Never mention hours, ingredients, nutrition, "
          "delivery times or sponsorship details unless a fact states them. Never name a person unless the asset type is "
          "association. Never use a fact marked out of date. Voice: friendly, plain, short sentences. Answer first, facts early. "
          "Do not use em dashes or en dashes. Return only JSON: {\"patch\": {\"section_id\": \"<the target section id>\", "
          "\"op\": \"insert or replace, as given\", \"text\": \"<markdown section, or the email or reply body>\"}, "
          "\"sentences\": [{\"text\": \"<each sentence of patch.text, verbatim>\", \"fact_ids\": [\"F12\"]}], "
          "\"rationale\": \"<one sentence>\"}")

ASSET_GUIDE = {
    "owned_patch": "A short section for an existing Little Caesars page: a heading plus 2 to 4 sentences that answer the target prompts.",
    "answer_page": "A new answer page: a heading that restates the question, then 3 to 5 sentences that answer it with the facts.",
    "moment_page": "A short FAQ section for the menu item in the moment: a heading plus 2 to 4 sentences. Do not name any person.",
    "association": "One caption sentence that connects the named person's post to the menu item, plus one fact sentence.",
    "correction_email": "A polite correction email to the author: first line 'Subject: ...', then 3 to 5 sentences with the current "
                        "fact and the source of truth link.",
    "community_reply": "A short, disclosed brand reply that starts with 'Little Caesars here.', 2 or 3 factual sentences, no marketing.",
}


def _fact_line(f, old=False):
    tail = f"ended {f['valid_to']}, out of date, do not use" if old else f"since {f['valid_from']}"
    return f"- {f['fact_id']}: {f['subject_name']} {f['attribute']} = {f['value']} ({tail}; source {f.get('source_url') or 'n/a'})"


def draft_messages(req, feedback=None):
    p, c = req.get("passage") or {}, req.get("claim") or {}
    lines = [f"Asset type: {req['asset_type']}. {ASSET_GUIDE[req['asset_type']]}",
             f"Issue: {req['issue_title']}",
             f"What AI said: {c.get('text') or 'n/a'} (tag {c.get('tag') or 'n/a'})",
             f"Cited passage ({p.get('domain', 'none')}, {p.get('owner_class', 'model memory')}, last updated "
             f"{p.get('last_updated', 'n/a')}): {p.get('excerpt') or 'none'}",
             "Target prompts:", *[f"- {t}" for t in req["prompts"]],
             f"Target section id: {req['section_id']} (op {req['op']})",
             "Current section:", req.get("section_before") or "(empty, new page)"]
    if req.get("recipient"):
        lines.append(f"Recipient: the author at {req['recipient']}")
    if req.get("persona_name"):
        lines.append(f"Person in the moment: {req['persona_name']}")
    lines += ["Facts you may use:", *[_fact_line(f) for f in req["facts"]]]
    if req.get("superseded"):
        lines += ["Out of date facts:", *[_fact_line(f, old=True) for f in req["superseded"]]]
    if feedback:
        lines.append("Your last draft failed these checks; fix them: " + "; ".join(feedback))
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "\n".join(lines)}]


def parse_draft(text):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.MULTILINE)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise DraftError(f"not JSON: {raw[:80]}") from e
    p = obj.get("patch") if isinstance(obj, dict) else None
    if not isinstance(p, dict) or p.get("op") not in ("insert", "replace") or not str(p.get("text") or "").strip() \
            or not p.get("section_id"):
        raise DraftError("patch needs section_id, op insert|replace and text")
    sents = [{"text": clean_dashes(str(s.get("text", ""))).strip(), "fact_ids": [str(x) for x in s.get("fact_ids") or []]}
             for s in obj.get("sentences") or [] if isinstance(s, dict)]
    return {"patch": {"section_id": str(p["section_id"]), "op": p["op"], "text": clean_dashes(p["text"])},
            "sentences": sents, "rationale": clean_dashes(str(obj.get("rationale") or ""))}


def draft_fix(req, chat, endpoint, feedback=None):
    msgs = draft_messages(req, feedback)
    try:
        return parse_draft(chat.complete(endpoint, msgs, max_tokens=1200, usage_context=usage_context("drafter")))
    except DraftError:
        msgs = msgs + [{"role": "user", "content": "Return only the JSON object."}]
        return parse_draft(chat.complete(endpoint, msgs, max_tokens=1200, usage_context=usage_context("drafter")))


def draft_claims_messages(text, subjects):
    return [{"role": "system", "content": "List every factual statement in this draft web text as a JSON list of "
                                          "{text, subject, attribute, stated_value}. subject is one of: " + ", ".join(subjects)
                                          + ". attribute is one of: " + ATTRIBUTES_TEXT + ". Return only the JSON list."},
            {"role": "user", "content": text}]


def unsupported_claims(text, grounding, chat, endpoint, subjects):
    out = chat.complete(endpoint, draft_claims_messages(text, subjects), max_tokens=800, usage_context=usage_context("draft_judge"))
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (out or "").strip(), flags=re.MULTILINE)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        items = None
    if not isinstance(items, list):   # fail closed: an unreadable judge answer never passes as "no unsupported claims"
        return ["The judge could not read this draft"]
    return [str(c.get("text")) for c in items if isinstance(c, dict) and not supported(c, grounding)]


def finalize_fix(draft, req, facts, rules, today, *, item_names, persona_names, judge=None):
    asset = req["asset_type"]
    if asset == "jsonld":
        errs = validate_against_facts(draft["patch"]["text"], facts, today)
        checks = [{"key": "schema", "ok": not errs, "label": "schema.org validation passed" if not errs else "; ".join(errs)}]
        sentences = [{**s, "kind": "fact"} for s in draft["sentences"]]
    else:
        checks, sentences = verify(draft, req, facts, today, item_names=item_names, persona_names=persona_names)
    grounding_ids = sorted({f for s in sentences for f in s["fact_ids"]})
    if judge is not None and asset != "jsonld":
        g = [f for f in facts if f["fact_id"] in grounding_ids]
        bad = judge(draft["patch"]["text"], g)
        checks.append({"key": "unsupported", "ok": not bad, "label": "No unsupported claims" if not bad else f"Unsupported claim: {bad[0]}"})
    rule = find_exclusion(draft["patch"]["text"], req.get("persona_id") if asset != "association" else None, [], rules)
    checks.append({"key": "policy", "ok": rule is None, "label": "Brand policy: no exclusion rule fires" if rule is None else f"Blocked by {rule}"})
    names_person = asset == "association" or any(p.lower() in draft["patch"]["text"].lower() for p in persona_names)
    ok = all(c["ok"] for c in checks if c["key"] in BLOCKING_CHECKS)
    return {"patch": draft["patch"], "sentences": sentences, "rationale": draft.get("rationale", ""),
            "tier": assign_tier(asset, names_person=names_person, checks_ok=ok), "state": "blocked" if rule else "pending_review",
            "checks": checks, "grounding_fact_ids": grounding_ids, "exclusion_rule_id": rule}
