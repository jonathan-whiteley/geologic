"""Moments from clear signals, each linked to the prompts it creates (spec 5.5). Quarantined signals never become moments."""
from __future__ import annotations
import hashlib
import inspect
import json
import re
from collections import defaultdict
from geologic.style import clean_dashes

TREND_VELOCITY = 3.0
TEXT_RESOLUTION_MIN = 0.9   # a persona post with no image match may still pass on a confident text resolution
MATCH_K = 5                 # prompt_idx hits looked at per question (Ruling S2-B)
QUESTION_SYSTEM = ("A social moment just happened for Little Caesars. Write the 1 or 2 questions real customers would now type "
                   "into an AI assistant because of it. Keep the occasion the post is about. Plain consumer wording, under 12 "
                   "words each, no hashtags. Return only a JSON list of strings.")


def _h(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def suggestion_id(question):
    """The prompt suggestion id a moment question gets when no prompt matches it."""
    return "s_" + _h(question.lower())


def persona_match_path(s) -> str | None:
    """How a real persona's post resolved to its menu item: "image" (the preferred path: a vision match), else "text"
    (no image match, but the item came from the post's text with resolution_confidence >= 0.9), else None (no moment).
    Smoke 1: the Goff photo got no image match, so the moment was dropped though the text named Deep!Deep! Dish."""
    if s.get("image_match_score"):
        return "image"
    if s.get("menu_item_id") and (s.get("resolution_confidence") or 0.0) >= TEXT_RESOLUTION_MIN:
        return "text"
    return None


def build_moments(signals, personas, menu):
    people = {p["persona_id"]: p for p in personas}
    items = {m["item_id"]: m for m in menu}
    groups = defaultdict(list)
    for s in signals:
        if s.get("quarantined") or s.get("menu_item_id") not in items:
            continue
        if s["source_type"] == "athlete_post" and s.get("is_real_persona") and persona_match_path(s):
            groups[("persona", s["persona_id"], s["menu_item_id"])].append(s)
        elif s["source_type"] == "social" and (s.get("velocity") or 0) >= TREND_VELOCITY:
            groups[("trend", None, s["menu_item_id"])].append(s)
    out = []
    for (kind, pid, iid), sigs in sorted(groups.items(), key=lambda kv: str(kv[0])):
        item, who = items[iid], (people.get(pid) or {}).get("display_name")
        out.append(dict(moment_id="mo_" + _h(f"{kind}|{pid}|{iid}"), kind=kind,
                        title=f"{who} posted a {item['name']} moment" if who else f"{item['name']} is trending",
                        signal_ids=sorted(s["signal_id"] for s in sigs), persona_id=pid, item_id=iid,
                        reach=max(s.get("reach") or 0 for s in sigs), velocity=max(s.get("velocity") or 0.0 for s in sigs),
                        image_match=max(s.get("image_match_score") or 0.0 for s in sigs) or None, questions=[], prompt_ids=[],
                        # not persisted: the post text the questions are written from (Ruling S2-B)
                        signal_texts=list(dict.fromkeys(s["text"].strip() for s in sorted(sigs, key=lambda s: s["signal_id"])
                                                        if (s.get("text") or "").strip())),
                        # not persisted (the moments table has no column for it); trends carry None
                        match_path=(("image" if any(persona_match_path(s) == "image" for s in sigs) else "text")
                                    if kind == "persona" else None)))
    return out


def question_messages(moment, item_name, persona_name=None):
    who = f"{persona_name} posted it. " if persona_name else ""
    posts = "".join(f'\nPost: "{clean_dashes(t)[:300]}"' for t in (moment.get("signal_texts") or [])[:3])
    return [{"role": "system", "content": QUESTION_SYSTEM},
            {"role": "user", "content": f"{who}Menu item: {item_name}. Moment: {moment['title']}.{posts}"}]


def parse_questions(text):
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip(), flags=re.MULTILINE)
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(obj, list):
        return []
    qs = [clean_dashes(q).strip()[:120] for q in obj if isinstance(q, str) and q.strip()]
    return qs[:2]


def fallback_question(item_name):
    return f"Where can I get {item_name}?"


def _hits(nearest, q):
    """nearest(q) may return one hit or a list; it is asked for MATCH_K hits when it takes k."""
    try:
        takes_k = "k" in inspect.signature(nearest).parameters
    except (TypeError, ValueError):
        takes_k = False
    res = nearest(q, k=MATCH_K) if takes_k else nearest(q)
    return [res] if isinstance(res, dict) else [h for h in res or [] if h]


def _tracked(hit):
    return hit.get("kind") == "tracked" if hit.get("kind") else not str(hit["id"]).startswith("s_")


def link_questions(questions, nearest, threshold):
    """Each question links to one prompt: the best tracked prompt at or above the threshold, else the best other
    suggestion at or above it, else a new suggestion. A question never matches its own earlier suggestion (smoke 2:
    the Goff questions matched themselves at 0.999 and never reached q202)."""
    ids, new = [], []
    for q in questions:
        own = suggestion_id(q)
        ok = sorted((h for h in _hits(nearest, q) if h["id"] != own and float(h.get("score") or 0.0) >= threshold),
                    key=lambda h: (not _tracked(h), -float(h["score"])))
        if ok:
            ids.append(ok[0]["id"])
        else:
            new.append((own, q))
            ids.append(own)
    return list(dict.fromkeys(ids)), new
