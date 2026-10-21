"""The v3 issue queue (spec 5.1): what is hurting our answers, decided by code from the latest answers, claims and moments.

No prompt, no issue: every issue names the tracked prompts it hurts, and a final guard drops any issue without one.
Rules run in a fixed order so a prompt already covered by an issue is not flagged again as a missing answer page:
(1) Wrong and Outdated claim groups, (2) stale owned pages, (3) Missing us, (4) Moment gap, (5) No answer page.
"""
from __future__ import annotations
import hashlib
from collections import Counter, defaultdict
from datetime import datetime
from geologic.claims import is_current
from geologic.datagen.reference import CLUSTER_LABELS, categories, is_branded
from geologic.style import clean_dashes

CLUSTER_PAGES = {"game_day_party": "pg_deals_game_day", "sponsorship": "pg_about", "ordering": "pg_order", "value": "pg_deals",
                 "dietary": "pg_nutrition", "comparison": "pg_menu", "product": "pg_menu"}
PRIORITY_WEIGHT = {"Gold": 3, "Silver": 2, "Bronze": 1}
TYPE_BONUS = {"outdated": 3, "wrong": 3, "moment_gap": 2, "missing_us": 1, "no_answer_page": 0}
LANE_BY_OWNER = {"Owned": "fix_page", "Editorial": "request_correction", "Reference": "request_correction",
                 "Community": "reply_as_brand", "Competitor": "counter_content"}
COMPETITOR_WORDS = ("domino", "pizza hut", "papa john")
MISSING_US_MIN_PROMPTS = 2
ENGINE_ORDER = ("Claude", "ChatGPT", "Gemini", "Meta AI")   # display order (Global Constraint 10)
MEMORY = "memory"


def claim_key(tag, source_doc_id, subject, attribute):
    return f"{tag}|{source_doc_id or 'memory'}|{subject}|{attribute}"


def _fix(asset_type, lane, page_id=None, section_id=None, op=None, recipient=None):
    return dict(asset_type=asset_type, lane=lane, page_id=page_id, section_id=section_id, op=op, recipient=recipient)


def _day(v):
    return v.date() if isinstance(v, datetime) else v


def _issue_id(issue_type, anchor, subject, attribute, scope):
    key = "|".join("" if x is None else str(x) for x in (issue_type, anchor, subject, attribute, scope))
    return "is_" + hashlib.sha1(key.encode()).hexdigest()[:10]


def _engines(names):
    seen = {n for n in names if n}
    return [e for e in ENGINE_ORDER if e in seen] + sorted(seen - set(ENGINE_ORDER))


def _most_common(values):
    counts = Counter(v for v in values if v is not None)
    return sorted(counts.items(), key=lambda kv: (-kv[1], str(kv[0])))[0][0] if counts else None


def _current_fact(facts, subject, attribute, today):
    cur = [f for f in facts if f["subject"] == subject and f["attribute"] == attribute and is_current(f, today)]
    return max(cur, key=lambda f: (f["valid_from"], f["fact_id"])) if cur else None


def _paren(value):
    return f" ({value})" if value not in (None, "") else ""


def _names_competitor_not_us(doc):
    """A third-party source (not owned, not a competitor's own site) that names a competitor and never names LCE."""
    if not doc or doc.get("owner_class") in ("Owned", "Competitor"):
        return False
    text = f"{doc.get('title') or ''} {doc.get('body') or ''}"
    return any(w in text.lower() for w in COMPETITOR_WORDS) and not is_branded(text)


def build_issues(answers, claims, prompts, sources, pages, facts, moments, personas, today):
    tracked = {p["prompt_id"]: p for p in prompts}
    docs = {d["doc_id"]: d for d in sources}
    owned = {d["doc_id"] for d in sources if d.get("owner_class") == "Owned"}
    is_owned = lambda doc_id: doc_id in owned or str(doc_id).startswith("lce_")
    names = {f["subject"]: f.get("subject_name") for f in facts}
    subject_name = lambda s: names.get(s) or str(s).replace("_", " ")
    cats = categories()
    menu_item = lambda s: s if cats.get(s) not in (None, "deal", "brand") else None

    by_prompt = defaultdict(list)
    for a in answers:
        if a.get("status", "ok") == "ok" and a.get("prompt_id") in tracked:
            by_prompt[a["prompt_id"]].append(a)
    tracked_claims = [c for c in claims if c.get("prompt_id") in tracked]

    def missed(a):   # the answer does not name LCE, or does not cite an owned page
        return not (a.get("lce_mentioned") and any(is_owned(d) for d in a.get("cited_doc_ids") or []))

    def named(pid):
        return sum(1 for a in by_prompt[pid] if a.get("lce_mentioned"))

    def main_cluster(pids):
        return _most_common(tracked[p].get("cluster") for p in pids)

    issues, covered = [], set()

    def emit(issue_type, *, title, prompt_ids, anchor, scope, action_lane, planned, cluster=None, source_doc_id=None,
             source_doc_ids=(), moment_id=None, persona_id=None, item_id=None, subject=None, attribute=None, fact_id=None,
             stated_fact_id=None, stated_value=None, engines=(), claim_keys=()):
        issues.append(dict(
            issue_id=_issue_id(issue_type, anchor, subject, attribute, scope), issue_type=issue_type, title=clean_dashes(title),
            cluster=cluster, source_doc_id=source_doc_id, source_doc_ids=list(source_doc_ids), moment_id=moment_id,
            persona_id=persona_id, item_id=item_id, subject=subject, attribute=attribute, fact_id=fact_id,
            stated_fact_id=stated_fact_id, stated_value=stated_value, prompt_ids=list(prompt_ids), engines=list(engines),
            missed_answers=None, action_lane=action_lane, planned=list(planned), claim_keys=list(claim_keys),
            score=None, rank=None, built_at=None))
        covered.update(prompt_ids)

    # (1) Wrong and Outdated claims, grouped by (tag, source or memory, subject, attribute)
    groups = defaultdict(list)
    for c in tracked_claims:
        if c.get("tag") in ("Wrong", "Outdated"):
            groups[(c["tag"], c.get("source_doc_id"), c.get("subject"), c.get("attribute"))].append(c)
    for (tag, src_id, subject, attribute), cs in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        pids = sorted({c["prompt_id"] for c in cs})
        cluster = main_cluster(pids)
        src = docs.get(src_id) if src_id else None
        owner = (src or {}).get("owner_class")
        value = _most_common(c.get("stated_value") for c in cs)
        cluster_page = CLUSTER_PAGES.get(cluster, "pg_menu")
        if owner == "Owned":
            planned = [_fix("owned_patch", "fix_page", page_id=src.get("page_id"), op="replace")]
        elif owner in ("Editorial", "Reference"):
            planned = [_fix("correction_email", "request_correction", section_id="email", op="insert", recipient=src.get("domain")),
                       _fix("owned_patch", "counter_content", page_id=cluster_page, op="insert")]
        elif owner == "Community":
            planned = [_fix("community_reply", "reply_as_brand", section_id="reply", op="insert")]
        elif owner == "Competitor":
            planned = [_fix("owned_patch", "counter_content", page_id=cluster_page, op="insert")]
        else:   # model memory (or a source we do not know): publish the right fact on an answer page per prompt
            planned = [_fix("answer_page", "publish_fact", page_id=f"pg_answer_{p}", section_id="main", op="insert") for p in pids]
        lane = LANE_BY_OWNER.get(owner, "publish_fact")
        what, attr = subject_name(subject), str(attribute).replace("_", " ")
        if tag == "Outdated":
            title = (f"{src['domain']} lists the {what} at an old {attr}{_paren(value)}" if src
                     else f"Engines state an old {what} {attr} from memory{_paren(value)}")
        else:
            title = (f"{src['domain']} states a wrong {what} {attr}{_paren(value)}" if src
                     else f"Engines state a wrong {what} {attr} from memory{_paren(value)}")
        fact = _current_fact(facts, subject, attribute, today)
        emit(tag.lower(), title=title, prompt_ids=pids, anchor=src_id or MEMORY, scope=cluster, action_lane=lane, planned=planned,
             cluster=cluster, source_doc_id=src_id, source_doc_ids=[src_id] if src_id else [], item_id=menu_item(subject),
             subject=subject, attribute=attribute, fact_id=fact["fact_id"] if fact else None,
             stated_fact_id=_most_common(c.get("fact_id") for c in cs) if tag == "Outdated" else None,
             stated_value=value, engines=_engines(c.get("engine") for c in cs),
             claim_keys=[claim_key(tag, src_id, subject, attribute)])

    # (2) Owned page stale: a current price fact newer than the page, and a tracked prompt with a claim about the subject
    # (cited or not: the Classic Pepperoni page never ranks, so requiring a citation would erase the story)
    by_subject = defaultdict(list)
    for c in tracked_claims:
        by_subject[c.get("subject")].append(c)
    page_doc = {d.get("page_id"): d["doc_id"] for d in sources if d.get("owner_class") == "Owned" and d.get("page_id")}
    for pg in sorted(pages, key=lambda p: p["page_id"]):
        subj, updated = pg.get("primary_subject"), _day(pg.get("updated_at"))
        fact = _current_fact(facts, subj, "price", today) if subj and by_subject.get(subj) else None
        if not fact or updated is None or not _day(fact["valid_from"]) > updated:
            continue
        cs = by_subject[subj]
        pids = sorted({c["prompt_id"] for c in cs})
        doc_id = page_doc.get(pg["page_id"], "lce_" + pg["page_id"])
        emit("outdated", title=f"Our {subject_name(subj)} page is out of date", prompt_ids=pids, anchor=doc_id,
             scope=pg["page_id"], action_lane="fix_page",
             planned=[_fix("jsonld", "fix_page", page_id=pg["page_id"], section_id="jsonld", op="replace")],
             cluster=main_cluster(pids), source_doc_id=doc_id, source_doc_ids=[doc_id], item_id=menu_item(subj), subject=subj,
             attribute="price", fact_id=fact["fact_id"], engines=_engines(c.get("engine") for c in cs))

    # (3) Missing us: a third-party source naming competitors, not LCE, cited on at least 2 tracked prompts of a cluster
    cites = defaultdict(lambda: defaultdict(set))
    for pid, ans in by_prompt.items():
        for a in ans:
            for d in set(a.get("cited_doc_ids") or []):
                cites[tracked[pid].get("cluster")][d].add(pid)
    for cluster in sorted(cites, key=str):
        qual = {d: ps for d, ps in cites[cluster].items() if len(ps) >= MISSING_US_MIN_PROMPTS and _names_competitor_not_us(docs.get(d))}
        if not qual:
            continue
        ranked = sorted(qual, key=lambda d: (-len(qual[d]), d))
        pids = sorted(set().union(*qual.values()))
        engines = _engines(a.get("engine") for p in pids for a in by_prompt[p] if set(a.get("cited_doc_ids") or []) & set(qual))
        emit("missing_us", title=f"{docs[ranked[0]].get('domain')} answers {CLUSTER_LABELS.get(cluster, cluster)} prompts without us",
             prompt_ids=pids, anchor=ranked[0], scope=cluster, action_lane="counter_content",
             planned=[_fix("answer_page", "counter_content", page_id=f"pg_answer_{cluster}", section_id="main", op="insert")],
             cluster=cluster, source_doc_id=ranked[0], source_doc_ids=ranked, engines=engines)

    # (4) Moment gap: a moment linked to a tracked prompt where at most 1 of 4 engines names LCE or no answer cites an
    # owned page. Links to suggestions only (not tracked yet) and discontinued items make no issue.
    people = {p["persona_id"]: p for p in personas}
    for m in sorted(moments, key=lambda m: m["moment_id"]):
        gone = _current_fact(facts, m.get("item_id"), "available", today)
        if gone and str(gone.get("value")).strip().lower() == "no":
            continue   # a discontinued item never gets a moment page (its stale claims still surface in rule 1)
        linked =[p for p in dict.fromkeys(m.get("prompt_ids") or []) if p in tracked]
        gaps = sorted(p for p in linked if by_prompt[p] and (named(p) <= 1 or not any(
            is_owned(d) for a in by_prompt[p] for d in a.get("cited_doc_ids") or [])))
        if not gaps:
            continue
        page = f"pg_moment_{m.get('item_id')}"
        planned = [_fix("moment_page", "capture_moment", page_id=page, section_id="main", op="insert")]
        person = people.get(m.get("persona_id"))
        if person and person.get("is_real") and person.get("approved_for_association") and not person.get("is_excluded"):
            planned.append(_fix("association", "capture_moment", page_id=page, section_id="association", op="insert"))
        cluster = main_cluster(gaps)
        emit("moment_gap", title=f"{m['title']}, and engines miss it", prompt_ids=gaps, anchor=m["moment_id"], scope=cluster,
             action_lane="capture_moment", planned=planned, cluster=cluster, moment_id=m["moment_id"],
             persona_id=m.get("persona_id"), item_id=m.get("item_id"),
             engines=_engines(a.get("engine") for p in gaps for a in by_prompt[p] if missed(a)))

    # (5) No answer page: an unbranded Gold or Silver tracked prompt not covered above, where no answer retrieved an
    # owned page and at most 1 of 4 engines names LCE
    for pid in sorted(tracked):
        p = tracked[pid]
        if p.get("branded") or p.get("priority") not in ("Gold", "Silver") or pid in covered or not by_prompt[pid]:
            continue
        if named(pid) > 1 or any(is_owned(d) for a in by_prompt[pid] for d in a.get("retrieved_doc_ids") or []):
            continue
        emit("no_answer_page", title=f"No Little Caesars page answers: {p['prompt_text']}", prompt_ids=[pid], anchor=None,
             scope=pid, action_lane="publish_fact",
             planned=[_fix("answer_page", "publish_fact", page_id=f"pg_answer_{pid}", section_id="main", op="insert")],
             cluster=p.get("cluster"), engines=_engines(a.get("engine") for a in by_prompt[pid] if missed(a)))

    out, seen = [], set()
    for i in issues:   # no prompt, no issue (should never trigger; the tests pin it)
        if not i["prompt_ids"] or i["issue_id"] in seen:
            print(f"dropping issue {i['issue_id']} ({i['issue_type']}): {'duplicate id' if i['issue_id'] in seen else 'no prompts'}")
            continue
        seen.add(i["issue_id"])
        i["missed_answers"] = sum(1 for p in i["prompt_ids"] for a in by_prompt[p] if missed(a))
        i["score"] = (TYPE_BONUS[i["issue_type"]] + sum(PRIORITY_WEIGHT.get(tracked[p].get("priority"), 0) for p in i["prompt_ids"])
                      + i["missed_answers"] / 4)
        out.append(i)
    out.sort(key=lambda i: (-i["score"], i["issue_id"]))
    for n, i in enumerate(out, start=1):
        i["rank"] = n
    return out
