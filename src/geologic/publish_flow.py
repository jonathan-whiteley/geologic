"""Publish and reset orchestration. Pure flow at the top; Delta/Lakebase stores below."""
from __future__ import annotations
import json
from geologic.exclusions import find_exclusion
from geologic.publish import next_page_version


def _already_applied(page: dict, suggestion: dict) -> bool:
    field = "jsonld" if suggestion["asset_type"] == "jsonld" else "body"
    return page.get(field) == suggestion["diff_after"]


FRIENDLY_ERROR = "Publish failed. Try again."


def publish(suggestion, store, rules, epoch, reprobe: bool = True) -> str:
    """Every state write is scoped to rows still 'publishing' (see DeltaStore.set_state). A failed or stale
    publish returns the row to 'pending_review' with a friendly error so Approve works again; the raw
    exception goes to stdout only."""
    sid = suggestion["suggestion_id"]
    in_review = suggestion["state"] in ("approved", "publishing")
    final_state = "published" if in_review else suggestion["state"]
    back_state = "pending_review" if in_review else suggestion["state"]

    def stale():
        print(f"publish {sid}: stale epoch, demo was reset")
        store.set_state(sid, back_state, FRIENDLY_ERROR)
        return "stale"

    if suggestion.get("epoch") != store.current_epoch():
        return stale()
    rule = find_exclusion(suggestion["diff_after"], suggestion.get("persona_id"), [], rules)
    if rule or suggestion.get("tier") == "BLOCKED":
        store.audit("publish_job", "blocked", sid, rule or suggestion.get("exclusion_rule_id"), "publish")
        store.set_state(sid, "blocked")
        return "blocked"

    try:
        page = store.get_page(suggestion["page_id"])
        applied = _already_applied(page, suggestion)
        if applied and suggestion["state"] == "auto_published":
            # Drafting job re-publishes live T0 rows on every run; never double-bump or re-sync.
            store.set_state(sid, final_state)
            return "published"
        store.set_step(sid, 1)
        if not applied:  # a retry after a partial failure skips the write but still syncs and re-probes
            if suggestion.get("epoch") != store.current_epoch():  # re-check right before writing (reset race)
                return stale()
            new = next_page_version(page, suggestion)
            store.write_page(new)
            store.record_version(new, sid)
        store.set_step(sid, 2)
        store.sync_index()
        store.set_step(sid, 3)
        if reprobe and suggestion.get("prompt_ids"):
            store.reprobe(list(suggestion["prompt_ids"]))
        store.set_step(sid, 5)
        if suggestion.get("epoch") != store.current_epoch():
            return stale()
        store.set_state(sid, final_state)
    except Exception as e:
        print(f"publish {sid} failed: {type(e).__name__}: {e}")
        store.set_state(sid, back_state, FRIENDLY_ERROR)
        store.audit("publish_job", "failed", sid, None, None)
        return "failed"
    return "published"


def reset(store) -> int:
    """Fast, visible steps first so the app is consistent quickly; the slow index sync runs last."""
    epoch = store.bump_epoch()      # first, so any in-flight probe or publish becomes stale
    store.clear_suggestions()       # clear + restore share one Lakebase transaction (restore commits)
    store.restore_suggestions(epoch)
    store.copy_baseline_probe(epoch)
    store.restore_pages()
    store.sync_index()
    return epoch


class DeltaStore:
    """site_pages/web_corpus in Delta, workflow state in Lakebase, index sync via VS, re-probe via the probe job."""
    def __init__(self, spark, conn, w):
        from geologic.config import settings as S
        self.spark, self.conn, self.w, self.S = spark, conn, w, S

    def current_epoch(self):
        return self.conn.execute("SELECT epoch FROM demo_state WHERE id = 1").fetchone()[0]

    def get_page(self, pid):
        return self.spark.table(self.S.fq("site_pages")).where(f"page_id = '{pid}'").first().asDict()

    def write_page(self, page):
        S, sp = self.S, self.spark
        sp.createDataFrame([page], sp.table(S.fq("site_pages")).schema).createOrReplaceTempView("new_page")
        sp.sql(f"MERGE INTO {S.fq('site_pages')} t USING new_page s ON t.page_id = s.page_id WHEN MATCHED THEN UPDATE SET *")
        sp.sql(f"""MERGE INTO {S.fq('web_corpus')} t USING new_page s ON t.doc_id = concat('lce_', s.page_id)
                   WHEN MATCHED THEN UPDATE SET t.body = concat(s.body, CASE WHEN s.jsonld IS NULL THEN '' ELSE concat('\n', s.jsonld) END)""")

    def record_version(self, page, by):
        self.conn.execute("INSERT INTO cms_page_versions (page_id, version, body, jsonld, published_by) VALUES (%s,%s,%s,%s,%s) "
                          "ON CONFLICT DO NOTHING", (page["page_id"], page["version"], page["body"], page["jsonld"], by))
        self.conn.commit()

    def set_state(self, sid, state, error=None):
        """Only touches a row still 'publishing': never a row reset has since restored, and never a T0 or
        blocked row the drafting job wrote in its final state."""
        self.conn.execute("UPDATE suggestions SET state = %s, error = %s WHERE suggestion_id = %s AND state = 'publishing'",
                          (state, error, sid))
        self.conn.commit()

    def set_step(self, sid, n):
        self.conn.execute("UPDATE suggestions SET publish_step = %s WHERE suggestion_id = %s", (n, sid))
        self.conn.commit()

    def audit(self, actor, action, ref, rule, point):
        self.conn.execute("INSERT INTO audit_events (actor, action, object_ref, exclusion_rule_id, enforcement_point) "
                          "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (actor, action, ref, rule, point))
        self.conn.commit()

    def sync_index(self):
        """Triggers a corpus index sync and waits for it to finish. The sync API refuses while the index
        pipeline is RUNNING, so wait for idle first, then trigger, then wait for the pipeline to go idle."""
        import time
        from databricks.vector_search.client import VectorSearchClient
        idx = VectorSearchClient(disable_notice=True).get_index(self.S.vs_endpoint, self.S.corpus_index)
        pid = idx.describe()["delta_sync_index_spec"]["pipeline_id"]

        def running():
            return str(self.w.pipelines.get(pid).state).upper().split(".")[-1] in ("RUNNING", "STARTING", "RESETTING")

        def wait_idle(limit_s=600):
            t0 = time.time()
            while running() and time.time() - t0 < limit_s:
                time.sleep(5)

        wait_idle()
        idx.sync()
        for _ in range(6):  # give the pipeline a moment to pick up the trigger
            time.sleep(5)
            if running():
                break
        wait_idle()

    def reprobe(self, prompt_ids):
        """Runs the targeted probe in-process (same interpreter, same Spark session) so the job
        finishes only after results land. run_probe.py sits next to this job's script."""
        import os, runpy, sys
        try:
            here = os.path.dirname(os.path.abspath(sys.modules["__main__"].__file__))
        except (AttributeError, KeyError, TypeError):
            here = os.getcwd()
        argv = sys.argv
        sys.argv = ["run_probe.py", "--mode", "targeted", "--prompt-ids", ",".join(prompt_ids), "--trigger", "publish"]
        try:
            runpy.run_path(os.path.join(here, "run_probe.py"), run_name="__main__")
        except SystemExit as e:
            if e.code not in (None, 0):
                raise RuntimeError(f"run_probe exited {e.code}")
        finally:
            sys.argv = argv


def baseline_source_sql(runs_table: str, base: str) -> str:
    """Run ids Reset copies: the baseline run plus later setup runs of the baseline run's own epoch."""
    return f"""(SELECT run_id FROM {runs_table} WHERE epoch = (SELECT epoch FROM {runs_table} WHERE run_id = '{base}') AND
               (run_id = '{base}' OR (trigger = 'setup' AND started_at >=
                    (SELECT started_at FROM {runs_table} WHERE run_id = '{base}'))))"""


class DeltaResetStore:
    def __init__(self, spark, conn, w):
        from geologic.config import settings as S
        self.spark, self.conn, self.w, self.S = spark, conn, w, S
        self._ds = DeltaStore(spark, conn, w)

    def bump_epoch(self):
        e = self.conn.execute("UPDATE demo_state SET epoch = epoch + 1 WHERE id = 1 RETURNING epoch").fetchone()[0]
        self.conn.commit()
        self.spark.sql(f"UPDATE {self.S.fq('probe_state')} SET current_epoch = {e} WHERE id = 1")
        return e

    def clear_suggestions(self):
        """No commit: restore_suggestions commits, so the app never sees an empty queue."""
        self.conn.execute("DELETE FROM suggestions"); self.conn.execute("DELETE FROM cms_page_versions")

    def restore_pages(self):
        S = self.S
        self.spark.sql(f"INSERT OVERWRITE {S.fq('site_pages')} SELECT * FROM {S.fq('site_pages_demo_start')}")
        self.spark.sql(f"""MERGE INTO {S.fq('web_corpus')} t USING {S.fq('web_corpus_demo_start')} s ON t.doc_id = s.doc_id
                           WHEN MATCHED AND t.body <> s.body THEN UPDATE SET t.body = s.body""")

    def sync_index(self):
        self._ds.sync_index()

    def restore_suggestions(self, epoch):
        rows = [r.asDict() for r in self.spark.table(self.S.fq("suggestions_baseline")).collect()]
        for r in rows:
            r["epoch"] = epoch
            r["checks"] = r["checks"] if isinstance(r["checks"], str) else json.dumps(r["checks"])
            r["prompt_ids"] = json.loads(r["prompt_ids"]) if isinstance(r["prompt_ids"], str) else r["prompt_ids"]
            cols = [c for c in r if c not in ("created_at",)]
            self.conn.execute(f"INSERT INTO suggestions ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})",
                              [r[c] for c in cols])
        self.conn.commit()

    def copy_baseline_probe(self, epoch):
        """Re-creates the demo-start probe picture under the new epoch: the baseline run plus any later setup
        runs of the baseline's own epoch (e.g. the post-T0 re-probe), keeping their original start times so the
        latest-response view resolves them in the same order."""
        S = self.S
        base = self.spark.table(S.fq("probe_state")).first()["baseline_run_id"]
        src = baseline_source_sql(S.fq("probe_runs"), base)
        self.spark.sql(f"""INSERT INTO {S.fq('probe_runs')} SELECT concat(run_id, '_e{epoch}'), {epoch}, run_type, 'reset', prompt_ids,
                           started_at, finished_at, status FROM {S.fq('probe_runs')} WHERE run_id IN {src}""")
        self.spark.sql(f"""INSERT INTO {S.fq('probe_responses')} SELECT concat(run_id, '_e{epoch}') AS run_id, {epoch} AS epoch,
                           * EXCEPT (run_id, epoch) FROM {S.fq('probe_responses')} WHERE run_id IN {src}""")
        latest = self.spark.sql(f"SELECT run_id FROM {S.fq('probe_runs')} WHERE epoch = {epoch} AND trigger = 'reset' "
                                "ORDER BY started_at DESC LIMIT 1").first()["run_id"]
        self.spark.sql(f"UPDATE {S.fq('probe_state')} SET latest_run_id = '{latest}' WHERE id = 1")
