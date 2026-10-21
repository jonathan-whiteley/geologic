"""Read models for each screen (v3). All warehouse SQL lives here; ids are checked against a pattern before they are
inlined, and every user value goes through :named parameters."""
import json
import os
import re
from datetime import date
from backend.warehouse import query
from geologic.brands import LOGOS
from geologic.datagen.prompts_ext import monthly_volume
from geologic.issues import claim_key

T = lambda n: f"{os.environ.get('CATALOG_NAME', 'jdub_demo')}.{os.environ.get('SCHEMA_NAME', 'geologic')}.{n}"
_PID = re.compile(r"^q\d{3}$")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")
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
