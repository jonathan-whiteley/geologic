"""Asserts the v3 planted stories (datagen.answer_key.ANSWER_KEY) against live state.

state keys: kpis (v_kpis row), issues (Delta issues rows), fixes (Lakebase fixes of the current epoch), moments, signals
(silver_signals joined to bronze: signal_id, author, producer, quarantined, quarantine_rule_id), audits (Lakebase audit_events:
exclusion_rule_id, enforcement_point, object_ref), public_signal_ids (v_public_signals ids), personas."""
from __future__ import annotations
import json
from geologic.datagen.answer_key import ANSWER_KEY as K, ENGINE_COUNT, TRACKED_COUNT
from geologic.verify import mentions, person_terms

ISSUE_STORIES = ("party_pack", "gameday_listicle", "classic_pepperoni", "reddit_price", "comparison_memory", "goff_moment")
ANSWER_RANGE = (114, 120)


def _checks(fix):
    c = fix.get("checks") or []
    return json.loads(c) if isinstance(c, str) else c


def _goff_moment(state):
    k = K["goff_moment"]
    return next((m for m in state["moments"] if m.get("persona_id") == k["persona_id"] and m.get("item_id") == k["item_id"]), None)


def _matches(story, issue, state):
    k = K[story]
    if issue.get("issue_type") != k["issue_type"]:
        return False
    if story == "party_pack":
        return (issue.get("source_doc_id") == k["source_doc_id"] and issue.get("subject") == k["subject"]
                and issue.get("fact_id") == k["truth_fact_id"] and issue.get("stated_fact_id") == k["stated_fact_id"])
    if story == "gameday_listicle":
        return k["source_doc_id"] in (issue.get("source_doc_ids") or [])
    if story == "classic_pepperoni":
        return issue.get("source_doc_id") == k["source_doc_id"]
    if story == "reddit_price":
        return issue.get("source_doc_id") == k["source_doc_id"] and issue.get("subject") == k["subject"]
    if story == "comparison_memory":
        return issue.get("cluster") == k["cluster"]
    if story == "goff_moment":
        m = _goff_moment(state)
        return m is not None and issue.get("moment_id") == m["moment_id"]
    return False


def _tiers(issue, fixes):
    return {f["asset_type"]: f["tier"] for f in fixes if f["issue_id"] == issue["issue_id"]}


def check(state) -> list[str]:
    f = []
    kp = state["kpis"]
    if kp.get("tracked_prompts") != TRACKED_COUNT:
        f.append(f"tracked prompts {kp.get('tracked_prompts')} != {TRACKED_COUNT}")
    if kp.get("engines") != ENGINE_COUNT:
        f.append(f"engines {kp.get('engines')} != {ENGINE_COUNT}")
    n = kp.get("answers")
    if n is None or not ANSWER_RANGE[0] <= n <= ANSWER_RANGE[1]:
        f.append(f"answers {n} not in [{ANSWER_RANGE[0]}, {ANSWER_RANGE[1]}]")

    fixes = state["fixes"]
    for story in ISSUE_STORIES:
        want = K[story]["fixes"]
        found = [i for i in state["issues"] if _matches(story, i, state)]
        if not found:
            f.append(f"{story}: no matching issue")
            continue
        issue = next((i for i in found if _tiers(i, fixes) == want), found[0])
        got = _tiers(issue, fixes)
        if got != want:
            f.append(f"{story}: fixes {got} != {want}")
        for fx in fixes:
            if fx["issue_id"] != issue["issue_id"]:
                continue
            for c in _checks(fx):
                if c.get("key") in ("grounded", "unsupported") and not c.get("ok"):
                    f.append(f"{story}: {fx['fix_id']} failed {c['key']}")

    goff = _goff_moment(state)
    if goff is None or K["goff_moment"]["prompt_id"] not in (goff.get("prompt_ids") or []):
        f.append(f"goff_moment: moment not linked to {K['goff_moment']['prompt_id']}")

    k = K["sportsbook_repost"]
    repost = [s for s in state["signals"] if s.get("author") == k["author"]]
    ids = {s["signal_id"] for s in repost}
    if not repost or not all(s.get("quarantined") and s.get("quarantine_rule_id") == k["rule_id"] for s in repost):
        f.append(f"sportsbook_repost: not quarantined by {k['rule_id']}")
    points = {a.get("enforcement_point") for a in state["audits"] if a.get("object_ref") in ids}
    f += [f"sportsbook_repost: no audit event at {p}" for p in k["enforcement_points"] if p not in points]
    if ids & set(state["public_signal_ids"]):
        f.append("sportsbook_repost: visible in public signals")
    if any(ids & set(m.get("signal_ids") or []) for m in state["moments"]):
        f.append("sportsbook_repost: feeds a moment")
    if any(w in (fx.get("patch_text") or "").lower() for fx in fixes for w in ("parlay", "sidelinebets")):
        f.append("sportsbook_repost: reached a draft")

    f += [f"issue without prompts: {i['issue_id']}" for i in state["issues"] if not i.get("prompt_ids")]
    f += [f"bad tier {fx.get('tier')} on {fx['fix_id']}" for fx in fixes if fx.get("tier") not in ("T0", "T1", "T2")]
    people = state["personas"]
    others = sorted(p["display_name"] for p in people if p.get("is_real") and p["display_name"] != "Jared Goff")
    if others:
        f.append(f"real people other than Jared Goff: {others}")
    terms = person_terms(people)
    f += [f"{fx['fix_id']} names a person outside the association review" for fx in fixes
          if fx.get("asset_type") != "association" and mentions(fx.get("patch_text") or "", terms)]
    return f
