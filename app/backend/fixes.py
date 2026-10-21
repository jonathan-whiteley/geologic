"""Fix workflow in Lakebase (replaces the v2 suggestions repo). claim() and claim_t0() are the only gates into 'publishing'."""
import json
from geologic.results import UPSERT_RESULT, result_values

_EPOCH = "(SELECT epoch FROM demo_state WHERE id = 1)"
CLAIM = f"""UPDATE fixes SET state = 'publishing', reviewer = %s, reviewed_at = now(), publish_step = 0, error = NULL
            WHERE fix_id = %s AND state = 'pending_review' AND epoch = {_EPOCH} RETURNING fix_id"""
CLAIM_T0 = f"""UPDATE fixes SET state = 'publishing', reviewer = %s, reviewed_at = now(), publish_step = 0, error = NULL
               WHERE tier = 'T0' AND state = 'pending_review' AND epoch = {_EPOCH} RETURNING fix_id"""
RELEASE = "UPDATE fixes SET state = 'pending_review', error = %s WHERE fix_id = %s AND state = 'publishing' RETURNING 1"
LIST = f"SELECT * FROM fixes WHERE epoch = {_EPOCH} AND state <> 'blocked' ORDER BY issue_rank, tier, asset_type"
TIER_COUNTS = f"SELECT tier, count(*) FROM fixes WHERE epoch = {_EPOCH} AND state = 'pending_review' GROUP BY tier"
# The quarantine count is of quarantined posts only (spec 5.2 "1 moment quarantined by policy"): object refs with an ingest
# event. Fixes blocked at draft or publish (object_ref = fix_id, no ingest event) are never counted and never shown here.
_QUARANTINED = "SELECT object_ref FROM audit_events WHERE enforcement_point = 'ingest' AND exclusion_rule_id IS NOT NULL"
QUARANTINE = ("SELECT count(DISTINCT object_ref) AS n, min(exclusion_rule_id) AS rule_id FROM audit_events "
              "WHERE enforcement_point = 'ingest' AND exclusion_rule_id IS NOT NULL")
POINTS = (f"SELECT enforcement_point, min(occurred_at) AS occurred_at FROM audit_events WHERE object_ref IN ({_QUARANTINED}) "
          "GROUP BY enforcement_point ORDER BY min(occurred_at)")
EDIT = """UPDATE fixes SET patch_text = %s, sentences = %s, grounding_fact_ids = %s, checks = %s, tier = %s, state = %s,
          exclusion_rule_id = %s, error = NULL WHERE fix_id = %s AND state = 'pending_review' RETURNING *"""


class FixRepo:
    def __init__(self, conn_factory):
        self._conn = conn_factory

    def _rows(self, sql, args=()):
        with self._conn() as c:
            cur = c.execute(sql, args)
            cols = [d.name for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]

    def _write(self, sql, args=()):
        """Runs one statement with RETURNING and commits; returns the returned rows as dicts."""
        with self._conn() as c:
            cur = c.execute(sql, args)
            cols = [d.name for d in cur.description] if cur.description else []
            rows = [dict(zip(cols, r)) for r in cur.fetchall()] if cols else []
            c.commit()
            return rows

    def _exec(self, sql, args=()):
        with self._conn() as c:
            c.execute(sql, args)
            c.commit()

    def epoch(self):
        return self._rows("SELECT epoch FROM demo_state WHERE id = 1")[0]["epoch"]

    def list(self):
        return self._rows(LIST)

    def get(self, fix_id):
        r = self._rows("SELECT * FROM fixes WHERE fix_id = %s", (fix_id,))
        return r[0] if r else None

    def claim(self, fix_id, reviewer) -> bool:
        return bool(self._write(CLAIM, (reviewer, fix_id)))

    def claim_t0(self, reviewer) -> list:
        return [r["fix_id"] for r in self._write(CLAIM_T0, (reviewer,))]

    def release(self, fix_id, error):
        return bool(self._write(RELEASE, (error, fix_id)))

    def release_many(self, ids, error):
        for i in ids:
            self.release(i, error)

    def set_run(self, ids, run_id):
        self._exec("UPDATE fixes SET publish_run_id = %s WHERE fix_id = ANY(%s)", (run_id, list(ids)))

    def reject(self, fix_id, reviewer) -> bool:
        return bool(self._write("UPDATE fixes SET state = 'rejected', reviewer = %s, reviewed_at = now() "
                                "WHERE fix_id = %s AND state = 'pending_review' RETURNING 1", (reviewer, fix_id)))

    def edit(self, fix_id, patch_text, final):
        r = self._write(EDIT, (patch_text, json.dumps(final["sentences"]), list(final["grounding_fact_ids"]), json.dumps(final["checks"]),
                               final["tier"], final["state"], final.get("exclusion_rule_id"), fix_id))
        return r[0] if r else None

    def status(self, fix_id):
        r = self._rows("SELECT state, publish_step, error, reviewed_at, tier FROM fixes WHERE fix_id = %s", (fix_id,))
        return r[0] if r else None

    def results(self, fix_id):
        return self._rows("SELECT * FROM fix_results WHERE fix_id = %s ORDER BY measured_at, prompt_id, engine", (fix_id,))

    def all_results(self):
        return self._rows("SELECT * FROM fix_results ORDER BY measured_at, fix_id, prompt_id, engine")

    def tier_counts(self) -> dict:
        with self._conn() as c:
            return {t: n for t, n in c.execute(TIER_COUNTS).fetchall()}

    def quarantine_points(self) -> dict:
        head = self._rows(QUARANTINE)[0]
        return {"count": head["n"] or 0, "rule_id": head["rule_id"], "points": self._rows(POINTS) if head["n"] else []}

    # The publish store protocol's Lakebase half (backend.warehouse_store.WarehouseStore delegates here)
    def set_state(self, fix_id, state, error=None):
        self._exec("UPDATE fixes SET state = %s, error = %s WHERE fix_id = %s AND state = 'publishing'", (state, error, fix_id))

    def set_step(self, fix_id, n):
        self._exec("UPDATE fixes SET publish_step = %s WHERE fix_id = %s AND state = 'publishing'", (n, fix_id))

    def audit(self, actor, action, ref, rule, point):
        self._exec("INSERT INTO audit_events (actor, action, object_ref, exclusion_rule_id, enforcement_point) "
                   "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (actor, action, ref, rule, point))

    def record_version(self, page, by):
        self._exec("INSERT INTO cms_page_versions (page_id, version, body, jsonld, published_by) VALUES (%s,%s,%s,%s,%s) "
                   "ON CONFLICT DO NOTHING", (page["page_id"], page["version"], page.get("body"), page.get("jsonld"), by))

    def save_results(self, rows):
        with self._conn() as c:
            for r in rows:
                c.execute(UPSERT_RESULT, result_values(r))
            c.commit()
