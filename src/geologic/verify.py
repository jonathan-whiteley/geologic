"""Deterministic checks on a structured draft (spec 5.4)."""
from __future__ import annotations
import re
from geologic.claims import is_current, split_sentences, values_match
from geologic.facts import parse_price
from geologic.tiering import T0_ASSETS

COMPETITORS = ("Domino's", "Dominos", "Pizza Hut", "Papa Johns", "Papa John's")
_NUM = re.compile(r"\$?\d+(?:\.\d{1,2})?")


def _norm(s):
    return " ".join(str(s or "").lower().split())


def _numbers(s):
    return [n for n in (parse_price(m) for m in _NUM.findall(str(s or "").replace(",", ""))) if n is not None]


def patch_sentences(text):
    out = []
    for line in (text or "").splitlines():
        line = line.strip().lstrip("-* ").strip()
        if line and not line.startswith("#"):
            out += split_sentences(line)   # menu names like "Deep!Deep! Dish" never split a sentence
    return out


def is_factual(sentence, names):
    low = sentence.lower()
    return bool(_numbers(sentence)) or any(n.lower() in low for n in names)


def _check(key, ok, good, bad):
    return {"key": key, "ok": bool(ok), "label": good if ok else bad}


def verify(draft, request, facts, today, *, item_names, persona_names):
    by_id = {f["fact_id"]: f for f in facts}
    declared = {_norm(s.get("text")): list(s.get("fact_ids") or []) for s in draft.get("sentences") or []}
    sents = [{"text": t, "fact_ids": declared.get(_norm(t), [])} for t in patch_sentences(draft["patch"]["text"])]
    names = tuple(item_names) + tuple(persona_names) + COMPETITORS
    ungrounded, bad_ids, mismatched, comp, people = [], [], [], [], []
    for s in sents:
        s["kind"] = "fact" if s["fact_ids"] else "copy"
        low = s["text"].lower()
        if not s["fact_ids"] and is_factual(s["text"], names):
            ungrounded.append(s["text"])
        cited = []
        for fid in s["fact_ids"]:
            f = by_id.get(fid)
            if f is None or not is_current(f, today):
                bad_ids.append(fid)
            else:
                cited.append(f)
        if cited:
            allowed = [n for f in cited for n in _numbers(f["value"]) + _numbers(f.get("subject_name"))]
            if any(all(abs(n - a) >= 0.01 for a in allowed) for n in _numbers(s["text"])):
                mismatched.append(s["text"])
            for item in (n for n in item_names if n.lower() in low):
                if not any(item.lower() in _norm(f.get("subject_name")) or item.lower() in _norm(f["value"]) for f in cited):
                    mismatched.append(s["text"])
        if any(c.lower() in low for c in COMPETITORS) and _numbers(s["text"]):
            comp.append(s["text"])
        if any(p.lower() in low for p in persona_names):
            people.append(s["text"])
    copies = [s for s in sents if s["kind"] == "copy"]
    t0 = request["asset_type"] in T0_ASSETS
    p = draft["patch"]
    checks = [
        _check("grounded", not ungrounded, "Every factual sentence maps to a fact", f"{len(ungrounded)} factual sentence(s) have no fact"),
        _check("current", not bad_ids, "Every fact is current in Unity Catalog", f"Unknown or out of date fact: {', '.join(sorted(set(bad_ids)))}"),
        _check("values", not mismatched, "Numbers and names match their facts exactly", "A number or name does not match its fact"),
        _check("comparison", not comp, "No competitor prices", "States a competitor price"),
        _check("persona", not people or request["asset_type"] == "association",
               "No person named outside the association review", "Names a person outside the association review"),
        _check("copy", not (t0 and copies), f"{len(copies)} sentence(s) are copy, no facts" if copies else "No copy without facts",
               "Copy without facts is not allowed in T0"),
        _check("target", (p["section_id"], p["op"]) == (request["section_id"], request["op"]), "Patch targets the planned section",
               f"Patch targets {p['section_id']} {p['op']}, planned {request['section_id']} {request['op']}"),
    ]
    return checks, sents


def supported(claim, grounding):
    sv = str(claim.get("stated_value") or "").strip()
    if not sv:
        return True
    return any(values_match(sv, f) or _norm(sv) in _norm(f["value"]) or _norm(f["value"]) in _norm(sv) for f in grounding)


def reground(patch_text, previous, facts, today, prior_ids=()):
    """Sentences for a human-edited patch (spec 5.4, Task 9 edit route). An unchanged sentence keeps its fact_ids. An
    edited sentence gets fact_ids re-derived by value matching against current brand_facts: for each number in it, the
    current facts whose value states that number, preferring facts whose subject_name the sentence names, then facts in
    prior_ids, else the single hit. No match leaves fact_ids empty, so verify() tags it copy, no facts (allowed for T1
    and T2, failed by the copy check for T0); a copy sentence that states a number or a name still fails grounded."""
    kept = {_norm(s.get("text")): list(s.get("fact_ids") or []) for s in previous or []}
    current, prior = [f for f in facts if is_current(f, today)], set(prior_ids)
    out = []
    for t in patch_sentences(patch_text):
        if _norm(t) in kept:
            out.append({"text": t, "fact_ids": kept[_norm(t)]})
            continue
        ids = set()
        for n in _numbers(t):
            hits = [f for f in current if any(abs(n - v) < 0.01 for v in _numbers(f["value"]))]
            named = [f for f in hits if f.get("subject_name") and _norm(f["subject_name"]) in _norm(t)]
            pick = named or [f for f in hits if f["fact_id"] in prior] or (hits if len(hits) == 1 else [])
            ids |= {f["fact_id"] for f in pick}
        out.append({"text": t, "fact_ids": sorted(ids)})
    return out
