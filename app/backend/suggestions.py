"""Suggestion workflow in Lakebase. claim() is the single atomic gate into 'publishing'."""
from geologic.lakebase import from_env

_COLS = ("suggestion_id, epoch, opp_id, opp_rank, title, asset_type, page_id, diff_before, diff_after, rationale, tier, state, "
         "checks, persona_id, prompt_ids, agent_trace_id, publish_step, error, reviewer")
_EPOCH = "(SELECT epoch FROM demo_state WHERE id = 1)"

class SuggestionRepo:
    _inst = None

    @classmethod
    def instance(cls, w):
        cls._inst = cls._inst or cls(from_env(w))
        return cls._inst

    def __init__(self, conn_factory):
        self._conn = conn_factory

    def _rows(self, sql, args=()):
        with self._conn() as c:
            cur = c.execute(sql, args)
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _write(self, sql, args):
        with self._conn() as c:
            r = c.execute(sql, args).fetchone()
            c.commit()
            return r is not None

    def list(self):
        return self._rows(f"SELECT {_COLS} FROM suggestions WHERE epoch = {_EPOCH} AND tier <> 'BLOCKED' "
                          "ORDER BY (tier = 'T0'), opp_rank, asset_type")

    def get(self, sid):
        r = self._rows(f"SELECT {_COLS} FROM suggestions WHERE suggestion_id = %s", (sid,))
        return r[0] if r else None

    def claim(self, sid, reviewer):
        return self._write(f"""UPDATE suggestions SET state = 'publishing', reviewer = %s, reviewed_at = now(), publish_step = 0, error = NULL
                               WHERE suggestion_id = %s AND state = 'pending_review' AND tier IN ('T1', 'T2') AND epoch = {_EPOCH}
                               RETURNING suggestion_id""", (reviewer, sid))

    def release(self, sid, error):
        """Undo a claim whose publish job never started: back to review, only if still 'publishing'."""
        return self._write("UPDATE suggestions SET state = 'pending_review', error = %s "
                           "WHERE suggestion_id = %s AND state = 'publishing' RETURNING 1", (error, sid))

    def set_run(self, sid, run_id):
        self._write("UPDATE suggestions SET publish_run_id = %s WHERE suggestion_id = %s RETURNING 1", (run_id, sid))

    def reject(self, sid, reviewer):
        return self._write("UPDATE suggestions SET state = 'rejected', reviewer = %s, reviewed_at = now() "
                           "WHERE suggestion_id = %s AND state = 'pending_review' RETURNING 1", (reviewer, sid))

    def status(self, sid):
        s = self.get(sid)
        return None if s is None else {"state": s["state"], "publish_step": s["publish_step"], "error": s["error"], "prompt_ids": s["prompt_ids"]}

    def save_proof(self, sid, title, reviewer, ba, summary):
        s = summary or {}
        vals = {"suggestion_id": sid, "title": title, "engine": ba.get("engine") or "Claude", "prompt_text": ba.get("prompt_text"),
                "before_answer": ba["before"]["answer"], "after_answer": ba["after"]["answer"],
                "before_cited": list(ba["before"].get("cited") or []), "after_cited": list(ba["after"].get("cited") or []),
                "share_before": s.get("share_before"), "share_after": s.get("share_after"),
                "accuracy_before": s.get("accuracy_before"), "accuracy_after": s.get("accuracy_after"), "reviewer": reviewer}
        try:
            self._upsert_proof(vals)
        except Exception as e:  # proof_results.prompt_text arrives with sql/v2_data_fixes.sql; until then save without it
            if "prompt_text" not in str(e):
                raise
            print(f"save_proof {sid}: no prompt_text column yet, saving without it")
            self._upsert_proof({k: v for k, v in vals.items() if k != "prompt_text"})

    def _upsert_proof(self, vals):
        cols = list(vals)
        updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "suggestion_id")
        self._write(f"""INSERT INTO proof_results ({", ".join(cols)}) VALUES ({", ".join(["%s"] * len(cols))})
                        ON CONFLICT (suggestion_id) DO UPDATE SET {updates}, saved_at = now()
                        RETURNING 1""", tuple(vals.values()))

    def latest_proof(self):
        cols = ("suggestion_id, title, engine, before_answer, after_answer, before_cited, after_cited, share_before, "
                "share_after, accuracy_before, accuracy_after, reviewer, saved_at")
        try:
            r = self._rows(f"SELECT {cols}, prompt_text FROM proof_results ORDER BY saved_at DESC LIMIT 1")
        except Exception as e:  # no prompt_text column until ops applies sql/v2_data_fixes.sql
            if "prompt_text" not in str(e):
                raise
            r = [{**row, "prompt_text": None} for row in self._rows(f"SELECT {cols} FROM proof_results ORDER BY saved_at DESC LIMIT 1")]
        return r[0] if r else None

    def latest_published_needing_proof(self):
        """Most recent publish of this epoch whose proof is missing or older than the publish (a rehearsal proof
        saved before a Reset and a new live publish). A proof saved after the publish is left alone."""
        r = self._rows(f"""SELECT s.suggestion_id, s.title, s.reviewer, s.prompt_ids FROM suggestions s
                           WHERE s.epoch = {_EPOCH} AND s.state = 'published'
                             AND NOT EXISTS (SELECT 1 FROM proof_results p WHERE p.suggestion_id = s.suggestion_id
                                             AND (s.reviewed_at IS NULL OR p.saved_at >= s.reviewed_at))
                           ORDER BY s.reviewed_at DESC NULLS LAST LIMIT 1""")
        return r[0] if r else None

    def live_page(self, page_id):
        # published_by holds the suggestion id for app publishes: show who approved it instead.
        r = self._rows("""SELECT v.version, COALESCE(s.reviewer, v.published_by) AS published_by, v.published_at
                          FROM cms_page_versions v LEFT JOIN suggestions s ON s.suggestion_id = v.published_by
                          WHERE v.page_id = %s ORDER BY v.version DESC LIMIT 1""", (page_id,))
        return r[0] if r else None
    def health(self):
        r = self._rows(f"""SELECT count(*) FILTER (WHERE state = 'auto_published') t0_auto,
                                  count(*) FILTER (WHERE tier = 'T2' AND state IN ('published', 'rejected')) t2_reviews,
                                  count(*) FILTER (WHERE tier = 'T1' AND state = 'published') t1_published,
                                  count(*) FILTER (WHERE tier = 'T1' AND state IN ('published', 'rejected')) t1_reviewed
                           FROM suggestions WHERE epoch = {_EPOCH}""")[0]
        blocked = self._rows("SELECT count(DISTINCT object_ref) n FROM audit_events WHERE action = 'blocked'")[0]["n"]
        pct = (100 * r["t1_published"] / r["t1_reviewed"]) if r["t1_reviewed"] else None
        return {"t0_auto": r["t0_auto"], "t1_approved_no_edit_pct": pct, "t2_reviews": r["t2_reviews"], "blocked": blocked}
