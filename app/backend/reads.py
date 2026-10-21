"""Read models for each screen (v3). All warehouse SQL lives here; ids are checked against a pattern before they are
inlined, and every user value goes through :named parameters."""
import json
import os
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlparse
from backend.warehouse import query
from geologic.brands import LOGOS
from geologic.claims import is_current, split_sentences
from geologic.datagen.prompts_ext import monthly_volume
from geologic.fixes import relevant_facts
from geologic.issues import claim_key
from geologic.photos import credit_for
from geologic.results import summarize

T = lambda n: f"{os.environ.get('CATALOG_NAME', 'jdub_demo')}.{os.environ.get('SCHEMA_NAME', 'geologic')}.{n}"
_PID = re.compile(r"^q\d{3}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")
_ISSUE_ID = re.compile(r"^is_[0-9a-f]{10}$")
ISSUE_FIELDS = "issue_id, rank, issue_type, title, cluster, action_lane, prompt_ids, missed_answers, moment_id"
EXCERPT_CHARS = 300
ENGINE_ORDER = ("Claude", "ChatGPT", "Gemini", "Meta AI")
CLAIM_FIELDS = ("claim_id", "text", "subject", "attribute", "stated_value", "tag", "fact_id", "source_doc_id")
DOC_FIELDS = "doc_id, domain, owner_class, title, url, last_updated"


def _in_list(ids):
    """Quoted SQL IN list of safe ids, or None when nothing safe remains (caller skips the query)."""
    ok = [i for i in ids or [] if isinstance(i, str) and _SAFE_ID.match(i)]
    return ",".join(f"'{i}'" for i in ok) or None


def _pct(row, *keys):
    """Views return rates as 0-1 fractions; the UI renders rates on a 0-100 scale."""
    for k in keys:
        if row.get(k) is not None:
            row[k] = row[k] * 100
    return row


def _engine_key(engine):
    return ENGINE_ORDER.index(engine) if engine in ENGINE_ORDER else len(ENGINE_ORDER)


def _unknown_doc(doc_id):
    return {"doc_id": doc_id, "domain": None, "owner_class": "Owned" if str(doc_id).startswith("lce_") else None,
            "title": doc_id, "url": None, "last_updated": None}


def excerpt(body, stated_value):
    """The sentence of a source that states the value (the quote shown in Fix), else the first EXCERPT_CHARS characters."""
    body = body or ""
    if stated_value:
        hit = next((t for t in split_sentences(body) if stated_value in t), None)
        if hit:
            return hit
    return body[:EXCERPT_CHARS]


def _fact_row(f, today):
    return {"fact_id": f["fact_id"], "subject_name": f.get("subject_name"), "attribute": f["attribute"], "value": f["value"],
            "valid_from": f["valid_from"], "valid_to": f.get("valid_to"), "current": is_current(f, today)}


PHASES = ("before", "after")
TOP_MOVERS = 5


def _monday(v):
    d = v.date() if isinstance(v, datetime) else date.fromisoformat(str(v)[:10])
    return d - timedelta(days=d.weekday())


def _mover(r):
    na, nb = r.get("naming_after") or 0, r.get("naming_before") or 0
    oa, ob = r.get("owned_cited_after") or 0, r.get("owned_cited_before") or 0
    return {"prompt_id": r["prompt_id"], "prompt_text": r.get("prompt_text"), "cluster": r.get("cluster"), "delta": (na - nb) + (oa - ob),
            "naming_before": nb, "naming_after": na, "owned_cited_before": ob, "owned_cited_after": oa}


def _safe(fn, default, what):
    try:
        return fn()
    except Exception as e:   # Lakebase blip or a missing fix_results table: the rest of Impact still renders
        print(f"impact {what}: {type(e).__name__}: {e}")
        return default


class Reads:
    _inst = None

    @classmethod
    def instance(cls):
        cls._inst = cls._inst or cls()
        return cls._inst

    # Measure
    def model_summary(self):
        kpis = _pct(query(f"SELECT * FROM {T('v_kpis')}")[0], "mention_rate", "owned_citation_share", "fact_accuracy",
                    "citation_rate")
        brands = [_pct({"brand": r["brand"], "logo": LOGOS.get(r["brand"]), "answer_share": r["answer_share"],
                        "avg_position": r["avg_position"], "citation_share": r["citation_share"]}, "citation_share")
                  for r in query(f"SELECT * FROM {T('v_leaderboard')} ORDER BY answer_share DESC")]
        heat = query(f"SELECT cluster, engine, answer_share FROM {T('v_cluster_engine_share')}")
        sources = [_pct({"owner_class": r["owner_class"], "citations": r["citations"], "share": r["share"]}, "share")
                   for r in query(f"SELECT owner_class, citations, share FROM {T('v_source_types')}")]
        domains = query(f"SELECT domain, owner_class, citations, prompts FROM {T('v_top_domains')} WHERE owner_class <> 'Owned' "
                        "ORDER BY citations DESC, domain LIMIT 5")
        return {"kpis": kpis, "brands": brands, "heatmap": heat, "source_types": sources, "top_domains": domains,
                "gateway": self.gateway_summary()}

    def prompt_rows(self):
        return query(f"""SELECT prompt_id, prompt_text, cluster, priority, branded, est_monthly_searches, engines_naming,
                                engines_owned_cited, engines_answered, answer_share, wrong_claims, outdated_claims, moment_id, moment_title
                         FROM {T('v_prompt_status')}
                         ORDER BY CASE priority WHEN 'Gold' THEN 0 WHEN 'Silver' THEN 1 ELSE 2 END, est_monthly_searches DESC, prompt_id""")

    def prompt_detail(self, prompt_id):
        if not _PID.match(prompt_id or ""):
            return None
        rows = query(f"SELECT * FROM {T('v_prompt_status')} WHERE prompt_id = :p", {"p": prompt_id})
        if not rows:
            return None
        return {**rows[0], "answers": self.scorecard(prompt_id)}

    def _docs(self, ids):
        safe = _in_list(sorted(set(ids)))
        return {d["doc_id"]: d for d in query(f"SELECT {DOC_FIELDS} FROM {T('web_corpus')} WHERE doc_id IN ({safe})")} if safe else {}

    def _issue_by_claim_key(self):
        out = {}
        for i in query(f"SELECT issue_id, claim_keys FROM {T('issues')}"):
            for k in i.get("claim_keys") or []:
                out.setdefault(k, i["issue_id"])
        return out

    def scorecard(self, prompt_id):
        """The latest answer per engine for one tracked prompt, in engine order, with cited doc chips and tagged claims
        (each claim carries the issue_id whose claim_keys hold it)."""
        if not _PID.match(prompt_id or ""):
            return []
        answers = query(f"SELECT answer_id, engine, status, answer, lce_mentioned, lce_rank, cited_doc_ids, retrieved_doc_ids "
                        f"FROM {T('v_latest_responses')} WHERE prompt_id = :p", {"p": prompt_id})
        claims = query(f"SELECT answer_id, {', '.join(CLAIM_FIELDS)} FROM {T('v_latest_claims')} WHERE prompt_id = :p", {"p": prompt_id})
        docs = self._docs(d for a in answers for d in a.get("cited_doc_ids") or [])
        issue_of = self._issue_by_claim_key() if claims else {}
        by_answer = {}
        for c in claims:
            key = claim_key(c["tag"], c.get("source_doc_id"), c["subject"], c["attribute"])
            by_answer.setdefault(c["answer_id"], []).append({k: c.get(k) for k in CLAIM_FIELDS} | {"issue_id": issue_of.get(key)})
        out = [{"engine": a["engine"], "status": a["status"], "answer": a.get("answer"), "lce_mentioned": a.get("lce_mentioned"),
                "lce_rank": a.get("lce_rank"), "cited": [docs.get(d) or _unknown_doc(d) for d in a.get("cited_doc_ids") or []],
                "owned_retrieved": any(str(d).startswith("lce_") for d in a.get("retrieved_doc_ids") or []),
                "claims": by_answer.get(a["answer_id"], [])} for a in answers]
        return sorted(out, key=lambda a: _engine_key(a["engine"]))

    def prompt_suggestions(self):
        return query(f"SELECT suggestion_id, prompt_text, cluster, source, moment_id FROM {T('prompt_suggestions')} "
                     "WHERE status = 'suggested' ORDER BY CASE source WHEN 'moment' THEN 0 ELSE 1 END, suggestion_id")

    def image_path(self, signal_id):
        r = query(f"SELECT image_uri FROM {T('v_public_signals')} WHERE signal_id = :s", {"s": signal_id})
        return r[0]["image_uri"] if r else None

    def gateway_summary(self):
        engines = query(f"""SELECT engine, count(*) AS answers FROM {T('v_latest_responses')}
                            WHERE status = 'ok' GROUP BY engine ORDER BY engine""")
        try:  # AI Gateway usage tracking, scoped to GEOlogic probe traffic (sql/gateway_views.sql)
            r = query(f"SELECT sum(requests) AS n FROM {T('v_gateway_usage')}")
            logged = r[0]["n"] if r and r[0]["n"] else None
        except Exception as e:  # view missing or system tables not readable: hide the count
            print(f"gateway_summary: {type(e).__name__}: {e}")
            logged = None
        return {"engines": engines, "answers": sum(e["answers"] for e in engines), "logged": logged}

    # Track and run
    def next_prompt_id(self):
        r = query(f"SELECT max(CAST(substr(prompt_id, 2) AS INT)) AS n FROM {T('prompts')} WHERE prompt_id RLIKE '^q3[0-9]{{2}}$'")
        n = r[0]["n"] if r else None
        return f"q{(n or 300) + 1}"

    def insert_prompt(self, row):
        """The prompts row plus its 12 question_volume_monthly rows, every value a parameter. tracked_by has no column in
        prompts (the v3 table), so it is logged only."""
        print(f"track {row['prompt_id']} by {row.get('tracked_by')}")
        query(f"""INSERT INTO {T('prompts')} (prompt_id, prompt_text, cluster, priority, branded, base_volume, calendar_tags, source,
                  tracked_at) VALUES (:prompt_id, :prompt_text, :cluster, :priority, :branded, :base_volume,
                  from_json(:calendar_tags, 'array<string>'), :source, current_timestamp())""",
              {k: row[k] for k in ("prompt_id", "prompt_text", "cluster", "priority", "branded", "base_volume", "source")}
              | {"calendar_tags": json.dumps(list(row.get("calendar_tags") or []))})
        vols = monthly_volume(row, date.today().replace(day=1))
        values = ", ".join(f"(:p, to_date(:m{i}), :v{i})" for i in range(len(vols)))
        params = {"p": row["prompt_id"]}
        for i, v in enumerate(vols):
            params[f"m{i}"], params[f"v{i}"] = v["month"].isoformat(), v["est_volume"]
        query(f"INSERT INTO {T('question_volume_monthly')} (prompt_id, month, est_volume) VALUES {values}", params)

    def suggestion(self, suggestion_id):
        if not _SAFE_ID.match(suggestion_id or ""):
            return None
        r = query(f"SELECT * FROM {T('prompt_suggestions')} WHERE suggestion_id = :s", {"s": suggestion_id})
        return r[0] if r else None

    def mark_suggestion_tracked(self, suggestion_id):
        if _SAFE_ID.match(suggestion_id or ""):
            query(f"UPDATE {T('prompt_suggestions')} SET status = 'tracked' WHERE suggestion_id = :s", {"s": suggestion_id})

    # Inputs of the edit route and the fast publisher
    def facts(self):
        from backend.warehouse_store import parse_facts
        return parse_facts(query(f"SELECT * FROM {T('brand_facts')}"))

    def rules(self):
        return query(f"SELECT * FROM {T('exclusion_rules')}")

    def item_names(self):
        rows = query(f"SELECT name, aliases FROM {T('menu_items')}")
        return sorted({n for m in rows for n in [m["name"], *(m.get("aliases") or [])] if n})

    def personas(self):
        return query(f"SELECT * FROM {T('personas')}")

    def focus(self, issue_id):
        """(subject, attribute) of an issue: results_rows keeps only claims about it."""
        if not _SAFE_ID.match(issue_id or ""):
            return None
        r = query(f"SELECT subject, attribute FROM {T('issues')} WHERE issue_id = :i", {"i": issue_id})
        return (r[0]["subject"], r[0]["attribute"]) if r and r[0]["subject"] and r[0]["attribute"] else None

    # Fix
    def issues(self, issue_type=None, cluster=None):
        where, params = [], {}
        if issue_type:
            where.append("issue_type = :t"); params["t"] = issue_type
        if cluster:
            where.append("cluster = :c"); params["c"] = cluster
        cond = f" WHERE {' AND '.join(where)}" if where else ""
        return query(f"SELECT {ISSUE_FIELDS} FROM {T('issues')}{cond} ORDER BY rank", params or None)

    def _moment(self, moment_id):
        m = query(f"SELECT * FROM {T('moments')} WHERE moment_id = :m", {"m": moment_id})
        if not m:
            return None
        m = m[0]
        # Public signals only: a quarantined post (the sportsbook repost) never reaches the UI.
        sids = _in_list(m.get("signal_ids"))
        sig = query(f"""SELECT signal_id, author, image_uri, image_match_score FROM {T('v_public_signals')}
                        WHERE signal_id IN ({sids}) ORDER BY (image_uri IS NULL), reach DESC LIMIT 1""") if sids else []
        sig = sig[0] if sig else {}
        person = query(f"SELECT display_name FROM {T('personas')} WHERE persona_id = :p", {"p": m["persona_id"]}) if m.get("persona_id") else []
        item = query(f"SELECT name FROM {T('menu_items')} WHERE item_id = :i", {"i": m["item_id"]}) if m.get("item_id") else []
        uri = sig.get("image_uri")
        return {"moment_id": m["moment_id"], "title": m["title"], "kind": m.get("kind"), "author": sig.get("author"),
                "persona_name": person[0]["display_name"] if person else None, "reach": m.get("reach"), "velocity": m.get("velocity"),
                "item_name": item[0]["name"] if item else m.get("item_id"),
                "image_url": f"/api/signals/{sig['signal_id']}/image" if uri else None, "image_credit": credit_for(uri),
                "image_match": m.get("image_match") if m.get("image_match") is not None else sig.get("image_match_score")}

    def issue_detail(self, issue_id, today=None):
        """Three blocks (spec 5.3): what AI said, what is true (brand_facts in Unity Catalog), and the fixes (added by the route)."""
        if not _ISSUE_ID.match(issue_id or ""):
            return None
        rows = query(f"SELECT * FROM {T('issues')} WHERE issue_id = :i", {"i": issue_id})
        if not rows:
            return None
        i, today = rows[0], today or date.today()
        pids = _in_list(i.get("prompt_ids"))
        texts = {r["prompt_id"]: r["prompt_text"] for r in query(f"SELECT prompt_id, prompt_text FROM {T('prompts')} "
                                                                 f"WHERE prompt_id IN ({pids})")} if pids else {}
        keys = set(i.get("claim_keys") or [])
        raw = query(f"SELECT engine, prompt_id, text, stated_value, tag, source_doc_id, subject, attribute FROM {T('v_latest_claims')} "
                    f"WHERE prompt_id IN ({pids})") if pids and keys else []
        claims = sorted(({"engine": c["engine"], "prompt_id": c["prompt_id"], "prompt_text": texts.get(c["prompt_id"]),
                          "text": c.get("text"), "stated_value": c.get("stated_value"), "tag": c["tag"]}
                         for c in raw if claim_key(c["tag"], c.get("source_doc_id"), c["subject"], c["attribute"]) in keys),
                        key=lambda c: (_engine_key(c["engine"]), c["prompt_id"]))
        passage = None
        if i.get("source_doc_id") and _SAFE_ID.match(i["source_doc_id"]):
            d = query(f"SELECT doc_id, domain, owner_class, last_updated, title, url, body FROM {T('web_corpus')} WHERE doc_id = :d",
                      {"d": i["source_doc_id"]})
            if d:
                d = d[0]
                passage = {k: d.get(k) for k in ("doc_id", "domain", "owner_class", "last_updated", "title", "url")}
                passage["excerpt"] = excerpt(d.get("body"), i.get("stated_value"))
        moment = self._moment(i["moment_id"]) if i.get("moment_id") else None
        scorecards = ([{"prompt_id": p, "prompt_text": texts.get(p), "answers": self.scorecard(p)} for p in i.get("prompt_ids") or []]
                      if i.get("issue_type") == "moment_gap" else [])
        facts = self.facts()
        subj, attr = i.get("subject"), i.get("attribute")
        if subj and attr:
            picked = [f for f in facts if f["subject"] == subj and f["attribute"] == attr]
        else:
            cur, old = relevant_facts(i, facts, today)
            picked = cur + old
        truth = sorted((_fact_row(f, today) for f in picked), key=lambda f: (not f["current"], f["fact_id"]))
        issue = {k: i.get(k) for k in ISSUE_FIELDS.split(", ")} | {k: i.get(k) for k in ("source_doc_id", "subject", "attribute", "stated_value")}
        return {"issue": issue,
                "said": {"claims": claims, "passage": passage, "memory": not i.get("source_doc_id") and i.get("issue_type") != "moment_gap",
                         "moment": moment, "scorecards": scorecards},
                "truth": {"facts": truth, "uc_table": T("brand_facts")}}

    # Impact
    def impact(self, repo):
        """Every Impact block. Rates are fractions 0..1 (Share of Model a decimal); counts are ints."""
        pm = {r["phase"]: r for r in query(f"SELECT * FROM {T('v_phase_metrics')}")}
        pc = {r["phase"]: r for r in query(f"SELECT * FROM {T('v_phase_claims')}")}
        n = lambda d, k: int(d.get(k) or 0)
        funnel = {ph: {k: n(pm.get(ph, {}), k) for k in ("answers", "mention_lce", "cite_lce", "pick_lce_first")} for ph in PHASES}
        leading = {ph: {"owned_retrieved": n(pm.get(ph, {}), "owned_retrieved"), "cite_lce": n(pm.get(ph, {}), "cite_lce"),
                        "wrong_or_outdated": n(pc.get(ph, {}), "wrong_or_outdated")} for ph in PHASES}
        lagging = {ph: {k: pm.get(ph, {}).get(k) for k in ("answer_share", "mention_rate", "avg_rank")} for ph in PHASES}
        weekly = query(f"SELECT week_start, brand, answer_share FROM {T('v_answer_share_weekly')} ORDER BY week_start, brand")

        epoch = _safe(repo.epoch, None, "epoch")
        results = _safe(repo.all_results, [], "fix_results")
        ledger = summarize(results, epoch) if results else []
        fixes = _safe(repo.list, [], "fixes")
        markers = [{"week_start": _monday(e["approved_at"]).isoformat(), "fix_id": e["fix_id"], "title": e["title"],
                    "approved_at": e["approved_at"], "rehearsal": e["rehearsal"]} for e in ledger if e.get("approved_at")]

        movers = [_mover(r) for r in query(f"SELECT * FROM {T('v_movers')}")]
        gains = sorted((m for m in movers if m["delta"] > 0), key=lambda m: (-m["delta"], m["prompt_id"]))[:TOP_MOVERS]
        drops = sorted((m for m in movers if m["delta"] < 0), key=lambda m: (m["delta"], m["prompt_id"]))[:TOP_MOVERS]

        status = query(f"SELECT prompt_id, cluster, engines_answered, engines_naming FROM {T('v_prompt_status')}")
        missed = {}
        for r in status:
            missed[r["cluster"]] = missed.get(r["cluster"], 0) + (r.get("engines_answered") or 0) - (r.get("engines_naming") or 0)
        missed_by_cluster = sorted(({"cluster": c, "missed": m} for c, m in missed.items() if m > 0), key=lambda x: (-x["missed"], x["cluster"]))

        tracked = {r["prompt_id"] for r in status}
        captured = {f["issue_id"] for f in fixes if f.get("state") == "published"}
        issue_of = {r["moment_id"]: r["issue_id"] for r in query(f"SELECT issue_id, moment_id FROM {T('issues')} WHERE moment_id IS NOT NULL")}
        live = [{"moment_id": m["moment_id"], "title": m["title"], "issue_id": issue_of.get(m["moment_id"]),
                 "prompt_ids": list(m.get("prompt_ids") or []), "tracked": any(p in tracked for p in m.get("prompt_ids") or [])}
                for m in query(f"SELECT moment_id, title, prompt_ids FROM {T('moments')} ORDER BY moment_id")
                if issue_of.get(m["moment_id"]) not in captured]

        return {"ledger": ledger, "funnel": funnel, "leading": leading, "lagging": lagging, "weekly": weekly, "markers": markers,
                "movers": {"gains": gains, "drops": drops}, "missed_by_cluster": missed_by_cluster, "live_moments": live,
                "patched_pages": self._patched_pages(fixes, ledger)}

    def _patched_pages(self, fixes, ledger):
        """lce_<page_id> of every published fix and every ledger entry with a page, most recently approved first (the UI
        defaults the citation tracker to the first one)."""
        page_of = {f["fix_id"]: f.get("page_id") for f in fixes if f.get("page_id")}
        latest = {}
        def seen(page_id, at):
            if page_id and _SAFE_ID.match(page_id):
                latest[page_id] = max(latest.get(page_id, ""), str(at or ""))
        for f in fixes:
            if f.get("state") == "published":
                seen(f.get("page_id"), f.get("reviewed_at"))
        for e in ledger:
            seen(page_of.get(e["fix_id"]), e.get("approved_at") or e.get("measured_at"))
        if not latest:
            return []
        ids = _in_list(sorted(latest))
        urls = {r["page_id"]: r["url"] for r in query(f"SELECT page_id, url FROM {T('site_pages')} WHERE page_id IN ({ids})")}
        def label(pid):
            if urls.get(pid):
                return urlparse(urls[pid]).path or urls[pid]
            return "/answers/" + pid.removeprefix("pg_").replace("_", "-")
        order = sorted(latest, key=lambda p: (latest[p], p), reverse=True)
        return [{"doc_id": f"lce_{p}", "label": label(p)} for p in order]

    def doc_citations(self, doc_id):
        if not _SAFE_ID.match(doc_id or ""):
            return None
        return query(f"SELECT started_at, citations, prompts, prompt_ids FROM {T('v_doc_citations')} WHERE doc_id = :d "
                     "ORDER BY started_at", {"d": doc_id})
