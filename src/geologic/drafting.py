"""Grounded drafter v2 (spec 5.4): structured section patches grounded in brand_facts, then verified by code."""
from __future__ import annotations
import json
import re
from geologic.exclusions import find_exclusion
from geologic.probe.engine import usage_context
from geologic.probe.judge import ATTRIBUTES_TEXT, _subject_line, _subject_lookup, _vocab, resolve_subject
from geologic.style import clean_dashes
from geologic.tiering import assign_tier
from geologic.verify import (CHECK_ORDER, jsonld_strings, mentions, only_quotes, person_terms, quoted_numbers, supported, verify,
                             verify_jsonld)

BLOCKING_CHECKS = {"grounded", "current", "values", "comparison", "persona", "copy", "target", "unsupported", "policy", "schema"}


class DraftError(ValueError):
    pass


SYSTEM = ("You are the Content Strategist for Little Caesars. You write one small change that is grounded in facts. "
          "Use only the facts provided, quote their values exactly, and list the fact ids behind every sentence in \"sentences\". "
          "patch.text is the published copy: no fact ids, brackets or citations in it. Never compute new numbers (totals, "
          "multiples, per-person math); state each fact value exactly as given. Never describe what an item is, contains or "
          "is made of, and never claim it is the only, first or best of anything, unless a fact states it. "
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
    if req.get("asset_type") not in ASSET_GUIDE:
        raise DraftError(f"no drafting guide for asset type {req.get('asset_type')}")
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


# Inline fact markers ("[F14]", "[F15, F12]") and bracket tags ("[Little Caesars]") are never published; markdown links stay.
_MARKER = re.compile(r"[ \t]*\[[^\]\n]{1,40}\](?!\()")


def _strip_markers(text):
    return "\n".join(re.sub(r"[ \t]{2,}", " ", _MARKER.sub("", line)).rstrip() for line in str(text).split("\n"))


def parse_draft(text):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.MULTILINE)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as e:
        raise DraftError(f"not JSON: {raw[:80]}") from e
    p = obj.get("patch") if isinstance(obj, dict) else None
    if not isinstance(p, dict) or p.get("op") not in ("insert", "replace") or not isinstance(p.get("text"), str) \
            or not p["text"].strip() or not p.get("section_id"):
        raise DraftError("patch needs section_id, op insert|replace and text")
    raw_sents = obj.get("sentences") or []
    if not isinstance(raw_sents, list):
        raise DraftError("sentences must be a list")
    sents = []
    for s in raw_sents:
        if not isinstance(s, dict):
            continue
        ids = s.get("fact_ids") or []
        if not isinstance(ids, list):
            raise DraftError("fact_ids must be a list of fact ids")
        sents.append({"text": _strip_markers(clean_dashes(str(s.get("text", "")))).strip(), "fact_ids": [str(x) for x in ids]})
    return {"patch": {"section_id": str(p["section_id"]), "op": p["op"], "text": _strip_markers(clean_dashes(p["text"]))},
            "sentences": sents, "rationale": clean_dashes(str(obj.get("rationale") or ""))}


def _blocking(final):
    return [c["label"] for c in final["checks"] if c["key"] in BLOCKING_CHECKS and not c["ok"]]


def draft_with_redrafts(draft_once, finalize, max_redrafts=2):
    """Draft, then redraft with the best draft's failed blocking checks as feedback, up to max_redrafts times. Keeps the
    finalized draft with the fewest blocking failures (a redraft never replaces a better one)."""
    final = finalize(draft_once(None))
    for _ in range(max_redrafts):
        bad = _blocking(final)
        if not bad:
            break
        f2 = finalize(draft_once(bad))
        if len(_blocking(f2)) < len(bad):
            final = f2
    return final


def draft_fix(req, chat, endpoint, feedback=None):
    msgs = draft_messages(req, feedback)
    try:
        return parse_draft(chat.complete(endpoint, msgs, max_tokens=1200, usage_context=usage_context("drafter")))
    except DraftError:
        msgs = msgs + [{"role": "user", "content": "Return only the JSON object."}]
        return parse_draft(chat.complete(endpoint, msgs, max_tokens=1200, usage_context=usage_context("drafter")))


def draft_claims_messages(text, subjects):
    """subjects are bare ids or subject_vocabulary() entries; the judge sees "id: display name (aliases)" lines, like the
    probe judge, so an item name is never read as another subject's id."""
    lines = "\n".join(_subject_line(*v) for v in _vocab(subjects))
    return [{"role": "system", "content": "List every factual statement in this draft web text as a JSON list of "
                                          "{text, subject, attribute, stated_value}. subject is the id of one of these "
                                          "subjects:\n" + lines + "\nattribute is one of: " + ATTRIBUTES_TEXT
                                          + ". Return only the JSON list."},
            {"role": "user", "content": text}]


def unsupported_claims(text, grounding, chat, endpoint, subjects, names=()):
    out = chat.complete(endpoint, draft_claims_messages(text, subjects), max_tokens=800, usage_context=usage_context("draft_judge"))
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (out or "").strip(), flags=re.MULTILINE)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        items = None
    if not isinstance(items, list):   # fail closed: an unreadable judge answer never passes as "no unsupported claims"
        return ["The judge could not read this draft"]
    lookup = _subject_lookup(subjects)
    norm = lambda c: {**c, "subject": resolve_subject(c.get("subject"), lookup)} if c.get("subject") else c
    return [str(c.get("text")) for c in items if isinstance(c, dict) and not supported(norm(c), grounding, names)]


_NO_JUDGE = {"key": "unsupported", "ok": False, "label": "Unsupported-claim check did not run"}


def _unsupported_check(text, grounding, judge, req=None):
    """The judge pass fails closed: no judge, or a judge that raises, is a failed check, never a silent pass. Two judge
    findings are expected, not unsupported: a correction quoting the wrong value it corrects (correction_email,
    community_reply), and an association caption naming its planned person."""
    if judge is None:
        return dict(_NO_JUDGE)
    try:
        bad = judge(text, grounding)
    except Exception:
        return dict(_NO_JUDGE)
    req = req or {}
    quoted = quoted_numbers(req)
    person = person_terms([req["persona_name"]]) if req.get("asset_type") == "association" and req.get("persona_name") else ()
    bad = [b for b in bad if not only_quotes(b, quoted) and not (person and mentions(b, person))]
    return {"key": "unsupported", "ok": not bad, "label": "No unsupported claims" if not bad else f"Unsupported claim: {bad[0]}"}


def finalize_fix(draft, req, facts, rules, today, *, item_names, persona_names, judge=None):
    """persona_names are names or persona rows. jsonld drafts get the T0 checks (verify_jsonld); every other asset gets
    verify() plus the judge pass. Checks come back in CHECK_ORDER; the tier is assigned by code from the results."""
    asset, text = req["asset_type"], draft["patch"]["text"]
    if asset == "jsonld":
        checks, sentences = verify_jsonld(draft, req, facts, today, persona_names=persona_names)
    else:
        checks, sentences = verify(draft, req, facts, today, item_names=item_names, persona_names=persona_names)
    grounding_ids = sorted({f for s in sentences for f in s["fact_ids"]})
    if asset != "jsonld":
        checks.append(_unsupported_check(text, [f for f in facts if f["fact_id"] in grounding_ids], judge, req))
    rule = find_exclusion(text, req.get("persona_id") if asset != "association" else None, [], rules)
    checks.append({"key": "policy", "ok": rule is None, "label": "Brand policy: no exclusion rule fires" if rule is None else f"Blocked by {rule}"})
    checks.sort(key=lambda c: CHECK_ORDER.index(c["key"]))
    terms = person_terms(list(persona_names or ()) + ([req["persona_name"]] if req.get("persona_name") else []))
    scanned = " \n ".join([text, *(s["text"] for s in sentences), *(jsonld_strings(text) if asset == "jsonld" else [])])
    names_person = asset == "association" or bool(mentions(scanned, terms))
    ok = all(c["ok"] for c in checks if c["key"] in BLOCKING_CHECKS)
    return {"patch": draft["patch"], "sentences": sentences, "rationale": draft.get("rationale", ""),
            "tier": assign_tier(asset, names_person=names_person, checks_ok=ok), "state": "blocked" if rule else "pending_review",
            "checks": checks, "grounding_fact_ids": grounding_ids, "exclusion_rule_id": rule}
