"""Moments from clear signals, each linked to the prompts it creates (spec 5.5). Quarantined signals never become moments."""
from __future__ import annotations
import hashlib
import json
import re
from collections import defaultdict
from geologic.style import clean_dashes

TREND_VELOCITY = 3.0
QUESTION_SYSTEM = ("A social moment just happened for Little Caesars. Write the 1 or 2 questions real customers would now type "
                   "into an AI assistant because of it. Plain consumer wording, under 12 words each, no hashtags. "
                   "Return only a JSON list of strings.")


def _h(s):
    return hashlib.sha1(s.encode()).hexdigest()[:10]


def build_moments(signals, personas, menu):
    people = {p["persona_id"]: p for p in personas}
    items = {m["item_id"]: m for m in menu}
    groups = defaultdict(list)
    for s in signals:
        if s.get("quarantined") or s.get("menu_item_id") not in items:
            continue
        if s["source_type"] == "athlete_post" and s.get("is_real_persona") and s.get("image_match_score"):
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
                        image_match=max(s.get("image_match_score") or 0.0 for s in sigs) or None, questions=[], prompt_ids=[]))
    return out


def question_messages(moment, item_name, persona_name=None):
    who = f"{persona_name} posted it. " if persona_name else ""
    return [{"role": "system", "content": QUESTION_SYSTEM},
            {"role": "user", "content": f"{who}Menu item: {item_name}. Moment: {moment['title']}."}]


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


def link_questions(questions, nearest, threshold):
    ids, new = [], []
    for q in questions:
        hit = nearest(q)
        if hit and hit["score"] >= threshold:
            ids.append(hit["id"])
        else:
            sid = "s_" + _h(q.lower())
            new.append((sid, q))
            ids.append(sid)
    return list(dict.fromkeys(ids)), new
