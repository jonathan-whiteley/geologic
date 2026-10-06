"""Suggestion workflow in Lakebase. claim() is the single atomic gate into 'publishing'."""
from geologic.lakebase import from_env

_COLS = ("suggestion_id, epoch, opp_id, opp_rank, title, asset_type, page_id, diff_before, diff_after, rationale, tier, state, "
         "checks, persona_id, prompt_ids, agent_trace_id, publish_step, error")
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

    def set_run(self, sid, run_id):
        self._write("UPDATE suggestions SET publish_run_id = %s WHERE suggestion_id = %s RETURNING 1", (run_id, sid))

    def reject(self, sid, reviewer):
        return self._write("UPDATE suggestions SET state = 'rejected', reviewer = %s, reviewed_at = now() "
                           "WHERE suggestion_id = %s AND state = 'pending_review' RETURNING 1", (reviewer, sid))

    def status(self, sid):
        s = self.get(sid)
        return None if s is None else {"state": s["state"], "publish_step": s["publish_step"], "error": s["error"], "prompt_ids": s["prompt_ids"]}

    def health(self):
        r = self._rows(f"""SELECT count(*) FILTER (WHERE state = 'auto_published') t0_auto,
                                  count(*) FILTER (WHERE tier = 'T2' AND state IN ('published', 'rejected')) t2_reviews,
                                  count(*) FILTER (WHERE tier = 'T1' AND state = 'published') t1_published,
                                  count(*) FILTER (WHERE tier = 'T1' AND state IN ('published', 'rejected')) t1_reviewed
                           FROM suggestions WHERE epoch = {_EPOCH}""")[0]
        blocked = self._rows("SELECT count(*) n FROM audit_events WHERE action = 'blocked'")[0]["n"]
        pct = (100 * r["t1_published"] / r["t1_reviewed"]) if r["t1_reviewed"] else None
        return {"t0_auto": r["t0_auto"], "t1_approved_no_edit_pct": pct, "t2_reviews": r["t2_reviews"], "blocked": blocked}
