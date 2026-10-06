"""Read models for each screen. All warehouse SQL lives here."""
import os
import re
from backend.warehouse import query
from geologic.brands import LOGOS
from geologic.photos import credit_for
from geologic.datagen.prompts_ext import THEME_LABELS

T = lambda n: f"{os.environ.get('CATALOG_NAME', 'jdub_demo')}.{os.environ.get('SCHEMA_NAME', 'geologic')}.{n}"
DRILL_TEXT = "How much is a Little Caesars Hot-N-Ready pizza right now?"
_PID = re.compile(r"^q\d{3}$")

def _pct(row, *keys):
    """Views return rates as 0-1 fractions; the UI renders rates on a 0-100 scale."""
    for k in keys:
        if row.get(k) is not None:
            row[k] = row[k] * 100
    return row

class Reads:
    _inst = None

    @classmethod
    def instance(cls):
        cls._inst = cls._inst or cls()
        return cls._inst

    def model_summary(self):
        kpis = _pct(query(f"SELECT * FROM {T('v_kpis')}")[0], "mention_rate", "citation_rate", "fact_accuracy")
        heat = query(f"SELECT cluster, engine, answer_share FROM {T('v_cluster_engine_share')}")
        brands = query(f"SELECT brand, answer_share FROM {T('v_brand_share')} ORDER BY answer_share DESC")
        last = query(f"SELECT max(r.finished_at) t FROM {T('probe_runs')} r JOIN {T('probe_state')} s ON r.epoch = s.current_epoch")[0]["t"]
        drill = query(f"SELECT prompt_id FROM {T('prompt_bank')} WHERE prompt_text = :t", {"t": DRILL_TEXT})[0]["prompt_id"]
        sources = [_pct(r, "share") for r in query(f"SELECT publisher, source_type, is_official, share FROM {T('v_citation_sources')} ORDER BY share DESC LIMIT 8")]
        top_q = query(f"SELECT * FROM {T('v_question_volume')} ORDER BY est_monthly_volume DESC, prompt_id LIMIT 5")
        leader = [_pct({**r, "logo": LOGOS.get(r["brand"])}, "citation_share") for r in query(f"SELECT * FROM {T('v_leaderboard')} ORDER BY answer_share DESC")]
        themes = [_pct({**r, "label": THEME_LABELS.get(r["theme"], r["theme"])}, "pct_positive", "pct_negative") for r in query(f"SELECT * FROM {T('v_theme_sentiment')}")]
        by_cluster = {r["cluster"]: r["p"] for r in query(f"SELECT cluster, min(prompt_id) p FROM {T('prompt_bank')} GROUP BY cluster")}
        return {"kpis": kpis, "heatmap": heat, "brands": brands, "leaderboard": leader, "themes": themes,
                "prompt_ids_by_cluster": by_cluster, "citation_sources": sources, "top_questions": top_q,
                "last_probe_at": last, "drill_prompt_id": drill}

    def prompt_detail(self, prompt_id):
        p = query(f"SELECT prompt_id, prompt_text, cluster FROM {T('v_prompts')} WHERE prompt_id = :p", {"p": prompt_id})
        if not p:
            return None
        rows = query(f"SELECT engine, answer, lce_rank, status, claims, cited_doc_ids FROM {T('v_latest_responses')} "
                     "WHERE prompt_id = :p ORDER BY engine", {"p": prompt_id})
        docs = {d["doc_id"]: d for d in query(f"SELECT doc_id, publisher, is_official FROM {T('web_corpus')}")}
        for r in rows:
            r["cited"] = [docs.get(d, {"doc_id": d, "publisher": "unknown", "is_official": False}) for d in r.pop("cited_doc_ids") or []]
        return {**p[0], "answers": rows}

    def signals(self, limit):
        sig = query(f"""SELECT s.*, m.name AS menu_item_name, pe.display_name AS persona_name
                        FROM {T('v_public_signals')} s LEFT JOIN {T('menu_items')} m ON m.item_id = s.menu_item_id
                        LEFT JOIN {T('personas')} pe ON pe.persona_id = s.persona_id
                        ORDER BY s.ingested_at DESC LIMIT {int(limit)}""")
        for s in sig:
            s["image_url"] = f"/api/signals/{s['signal_id']}/image" if s.get("image_uri") else None
            s["image_credit"] = credit_for(s.pop("image_uri", None))
        q = query(f"SELECT count(*) n FROM {T('silver_signals')} WHERE quarantined")[0]["n"]
        hour = query(f"""SELECT count(*) ingested, avg(CASE WHEN menu_item_id IS NOT NULL THEN 1 ELSE 0 END) matched_pct,
                         count(image_match_score) images FROM {T('v_public_signals')} WHERE ingested_at > now() - INTERVAL 1 HOUR""")[0]
        hour["new_opps"] = query(f"SELECT count(*) n FROM {T('gold_opportunities')} WHERE status = 'open'")[0]["n"]
        cal = query(f"SELECT name, start_ts, end_ts, volume_multiplier FROM {T('demand_calendar')} ORDER BY start_ts")
        return {"signals": sig, "quarantined_count": q, "last_hour": hour, "calendar": cal}

    def image_path(self, signal_id):
        r = query(f"SELECT image_uri FROM {T('v_public_signals')} WHERE signal_id = :s", {"s": signal_id})
        return r[0]["image_uri"] if r else None

    def opportunities(self):
        return query(f"SELECT * FROM {T('gold_opportunities')} ORDER BY rank")

    def weekly(self):
        return query(f"SELECT week_start, brand, answer_share FROM {T('v_answer_share_weekly')} ORDER BY week_start")

    def before_after(self, prompt_ids, engine="Claude"):
        """First and latest answer in the current epoch for the first affected prompt."""
        if not prompt_ids:
            return None
        rows = query(f"""SELECT pr.answer, pr.cited_doc_ids AS cited FROM {T('probe_responses')} pr
                         JOIN {T('probe_runs')} runs USING (run_id) JOIN {T('probe_state')} st ON pr.epoch = st.current_epoch
                         WHERE pr.prompt_id = :p AND pr.engine = :e AND pr.status = 'ok' ORDER BY runs.started_at""",
                     {"p": prompt_ids[0], "e": engine})
        return {"before": rows[0], "after": rows[-1]} if len(rows) >= 2 else None

    def cluster_before_after(self, prompt_ids):
        ids = [p for p in prompt_ids or [] if _PID.match(p)]
        if not ids:
            return None
        in_list = ",".join(f"'{p}'" for p in ids)
        # Share uses unbranded prompts only (same definition as the headline); accuracy uses all prompts.
        rows = query(f"""WITH e AS (
              SELECT pr.*, p.branded, ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at) AS first_rn,
                     ROW_NUMBER() OVER (PARTITION BY pr.prompt_id, pr.engine ORDER BY runs.started_at DESC) AS last_rn
              FROM {T('probe_responses')} pr JOIN {T('probe_runs')} runs USING (run_id)
              JOIN {T('probe_state')} st ON pr.epoch = st.current_epoch
              JOIN {T('v_prompts')} p ON p.prompt_id = pr.prompt_id
              WHERE pr.status = 'ok' AND pr.prompt_id IN ({in_list}))
            SELECT phase,
                   AVG(CASE WHEN NOT branded THEN CASE WHEN lce_mentioned AND lce_rank > 0 THEN 1.0 / lce_rank ELSE 0 END END) AS share,
                   SUM(size(filter(claims, c -> c.verdict = 'correct'))) /
                     NULLIF(SUM(size(filter(claims, c -> c.verdict IN ('correct', 'wrong')))), 0) AS acc
            FROM (SELECT *, 'before' AS phase FROM e WHERE first_rn = 1
                  UNION ALL SELECT *, 'after' AS phase FROM e WHERE last_rn = 1) x
            GROUP BY phase""")
        d = {r["phase"]: r for r in rows}
        return {"share_before": d.get("before", {}).get("share"), "share_after": d.get("after", {}).get("share"),
                "accuracy_before": _pct(d.get("before", {}), "acc").get("acc"), "accuracy_after": _pct(d.get("after", {}), "acc").get("acc")}

    # Prompt Explorer
    def _vs(self, text, k):
        from backend.deps import _w
        res = _w().vector_search_indexes.query_index(index_name=T("prompt_idx"), columns=["prompt_id", "prompt_text"],
                                                     query_text=text, num_results=k)
        return [r[0] for r in (res.result.data_array or [])]

    def prompt_search(self, q):
        ids = self._vs(q, 1)
        return ids[0] if ids else None

    def prompt_explorer(self, prompt_id):
        st = query(f"SELECT * FROM {T('v_prompt_status')} WHERE prompt_id = :p", {"p": prompt_id})
        if not st:
            return None
        s = st[0]
        series = query(f"SELECT month, est_volume FROM {T('question_volume_monthly')} WHERE prompt_id = :p ORDER BY month", {"p": prompt_id})
        rel_ids = [i for i in self._vs(s["prompt_text"], 7) if i != prompt_id][:5]
        rel = {r["prompt_id"]: r for r in query(f"SELECT prompt_id, prompt_text, avg_monthly_volume, tracked FROM {T('v_prompt_status')} "
                                                 f"WHERE prompt_id IN ({','.join(repr(i) for i in rel_ids if i.isalnum()) or 'NULL'})")}
        related = [{"prompt_id": i, "prompt_text": rel[i]["prompt_text"], "avg_monthly_volume": rel[i]["avg_monthly_volume"],
                    "status": "closest" if n == 0 else ("tracking" if rel[i]["tracked"] else "track")}
                   for n, i in enumerate(i for i in rel_ids if i in rel)]
        detail = self.prompt_detail(prompt_id) if s["tracked"] else None
        truth = ("Menu: Classic Hot-N-Ready Pepperoni $6.49 · Online gameday deal $4.99" if s["cluster"] == "value" else None)
        return {"prompt_id": prompt_id, "prompt_text": s["prompt_text"], "cluster": s["cluster"], "tracked": s["tracked"],
                "first_tracked": s["first_tracked"], "updated_at": s["updated_at"], "menu_truth": truth,
                "kpis": {k: s[k] for k in ("avg_monthly_volume", "volume_tier", "answer_share", "engines_naming", "engines_answered")},
                "series": series, "related": related, "answers": detail["answers"] if detail else []}

    def track_prompt(self, prompt_id, user):
        if not query(f"SELECT 1 FROM {T('v_prompts')} WHERE prompt_id = :p", {"p": prompt_id}):
            return False
        query(f"INSERT INTO {T('tracked_prompts')} VALUES (:p, :u, current_timestamp())", {"p": prompt_id, "u": user})
        return True
