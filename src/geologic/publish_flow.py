"""Publish and reset orchestration (v3). Pure flow at the top; the Spark-backed job stores below.

publish_fix: policy re-check, section patch on the page, vector upsert, targeted re-ask, fix_results rows. Every state write
goes through store.set_state, which only touches a row still 'publishing', so a Reset that restored the row always wins."""
from __future__ import annotations
import json
import re
import time
from geologic.exclusions import find_exclusion
from geologic.fixes import EXTERNAL_ASSETS, NEW_PAGE_URL
from geologic.patches import apply_patch
from geologic.results import results_rows

FRIENDLY_ERROR = "Publish failed. Try again."
STEP_LABELS = ("Policy re-check", "Patch the page", "Update the vector index", "Re-ask the engines", "Record before and after")
_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")


def apply_fix_to_page(page, fix, now):
    new = dict(page)
    if fix["asset_type"] == "jsonld":
        new["jsonld"], new["has_valid_jsonld"] = fix["patch_text"], True
    else:
        new["body"] = apply_patch(page.get("body") or "", {"section_id": fix["section_id"], "op": fix["op"], "text": fix["patch_text"]})
    new["version"], new["updated_at"] = (page.get("version") or 0) + 1, now
    return new


def already_applied(page, fix):
    """True when the page already carries this fix's patch (a retry after a failed re-ask): skip the write and the version
    bump, still upsert the doc and re-ask. jsonld compares the whole JSON-LD; text patches look for the patch text."""
    if not page:
        return False
    if fix["asset_type"] == "jsonld":
        return page.get("jsonld") == fix["patch_text"]
    return fix["patch_text"].strip("\n") in (page.get("body") or "")


def new_page(fix, now):
    slug = fix["page_id"].removeprefix("pg_").replace("_", "-")
    return dict(page_id=fix["page_id"], url=NEW_PAGE_URL.format(slug=slug), page_type="answer", primary_item_id=None,
                primary_subject=None, body="", jsonld=None, has_valid_jsonld=False, version=0, updated_at=now)


def corpus_doc(page):
    body = (page.get("body") or "") + (f"\n{page['jsonld']}" if page.get("jsonld") else "")
    return dict(doc_id=f"lce_{page['page_id']}", title=page["url"], body=body, owner_class="Owned", domain="littlecaesars.com",
                url=page["url"], page_id=page["page_id"], last_updated=page.get("updated_at"))


def _policy(fix, rules):
    return find_exclusion(fix["patch_text"], fix.get("persona_id") if fix["asset_type"] != "association" else None, [], rules)


class _Stale(Exception):
    pass


def _stale(fix, store):
    print(f"publish {fix['fix_id']}: stale epoch, demo was reset")
    store.set_state(fix["fix_id"], "pending_review", FRIENDLY_ERROR)
    return "stale"


def _failed(fix, store, e):
    print(f"publish {fix['fix_id']} failed: {type(e).__name__}: {e}")
    store.set_state(fix["fix_id"], "pending_review", FRIENDLY_ERROR)
    store.audit("publish_job", "failed", fix["fix_id"], None, None)
    return "failed"


def _gate(fix, store, rules):
    """Steps before the page write: epoch, policy re-check, external lanes. Returns an outcome, or None to continue."""
    fid = fix["fix_id"]
    if fix.get("epoch") != store.current_epoch():
        return _stale(fix, store)
    store.set_step(fid, 1)
    rule = _policy(fix, rules)
    if rule:
        store.audit("publish_job", "blocked", fid, rule, "publish")
        store.set_state(fid, "blocked")
        return "blocked"
    if fix["asset_type"] in EXTERNAL_ASSETS:   # a human sends the email or reply; no page change, no re-ask
        store.set_state(fid, "approved")
        return "approved"
    return None


def _patch(fix, store, now):
    """Steps 2 and 3. A page that already carries the patch (a retry) is not written or versioned again."""
    fid = fix["fix_id"]
    store.set_step(fid, 2)
    page = store.get_page(fix["page_id"]) or new_page(fix, now)
    if already_applied(page, fix):
        new = page
    else:
        new = apply_fix_to_page(page, fix, now)
        if fix.get("epoch") != store.current_epoch():   # re-check right before writing (Reset race)
            raise _Stale()
        store.write_page(new)
        store.record_version(new, fid)
    store.set_step(fid, 3)
    store.upsert_doc(corpus_doc(new))


def _texts(*maps):
    return {p: v["answer"].get("prompt_text") for m in maps for (p, _e), v in m.items()
            if (v.get("answer") or {}).get("prompt_text")}


def _record(fix, store, before, after, now, clock, focus):
    fid = fix["fix_id"]
    store.set_step(fid, 5)
    if fix.get("epoch") != store.current_epoch():
        raise _Stale()
    store.save_results(results_rows(fix, before, after, now=now, approved_at=fix.get("reviewed_at"),
                                    elapsed_s=(clock() - now).total_seconds() if clock else None,
                                    prompt_texts=_texts(before, after), focus=focus))
    store.set_state(fid, "published")


def publish_fix(fix, store, rules, *, now, clock=None, focus=None) -> str:
    out = _gate(fix, store, rules)
    if out:
        return out
    try:
        _patch(fix, store, now)
        store.set_step(fix["fix_id"], 4)
        pids = list(fix["prompt_ids"])
        before = store.latest(pids)
        after = store.reask(pids)
        _record(fix, store, before, after, now, clock, focus)
    except _Stale:
        return _stale(fix, store)
    except Exception as e:
        return _failed(fix, store, e)
    return "published"


def publish_batch(fixes, store, rules, *, now, focus_by_issue=None, clock=None) -> dict:
    """The T0 batch: per-fix gate and page steps (a failure marks only that fix), then one latest and one re-ask over the
    sorted union of the remaining fixes' prompts, then results and 'published' per fix."""
    focus_by_issue = focus_by_issue or {}
    outcomes, going = {}, []
    for fix in fixes:
        out = _gate(fix, store, rules)
        if out:
            outcomes[fix["fix_id"]] = out
            continue
        try:
            _patch(fix, store, now)
            going.append(fix)
        except _Stale:
            outcomes[fix["fix_id"]] = _stale(fix, store)
        except Exception as e:
            outcomes[fix["fix_id"]] = _failed(fix, store, e)
    if not going:
        return outcomes
    try:
        for fix in going:
            store.set_step(fix["fix_id"], 4)
        pids = sorted({p for fix in going for p in fix["prompt_ids"]})
        before = store.latest(pids)
        after = store.reask(pids)
    except Exception as e:
        return {**outcomes, **{fix["fix_id"]: _failed(fix, store, e) for fix in going}}
    for fix in going:
        try:
            _record(fix, store, before, after, now, clock, focus_by_issue.get(fix["issue_id"]))
            outcomes[fix["fix_id"]] = "published"
        except _Stale:
            outcomes[fix["fix_id"]] = _stale(fix, store)
        except Exception as e:
            outcomes[fix["fix_id"]] = _failed(fix, store, e)
    return outcomes


def reset(store) -> int:
    """Lakebase first (epoch, queue), then the probe picture, then pages and prompts with their vectors.
    fix_results is never touched: a rehearsal survives Reset and is the 90 s fallback."""
    epoch = store.bump_epoch()      # first, so any in-flight publish becomes stale
    store.restore_fixes(epoch)
    store.clear_page_versions()
    store.copy_baseline_probe(epoch)
    extra_docs = store.restore_pages()
    store.restore_source_vectors(extra_docs)
    extra_prompts = store.restore_prompts()
    store.restore_prompt_vectors(extra_prompts)
    return epoch


def _in_list(ids):
    ok = [i for i in ids or [] if isinstance(i, str) and _SAFE_ID.match(i)]
    return ",".join(f"'{i}'" for i in ok) or None


def wait_visible(retriever, doc, limit_s=10, sleep=time.sleep):
    """Freshness guard after a Direct Vector Access upsert: poll until the doc is a hit for its own text (at most limit_s)."""
    for _ in range(int(limit_s)):
        try:
            if any(d.doc_id == doc["doc_id"] for d in retriever.search((doc.get("body") or "")[:500], 3)):
                return True
        except Exception as e:
            print(f"vector freshness: {type(e).__name__}: {e}")
        sleep(1)
    print(f"vector freshness: not visible after {limit_s} s")
    return False


class DeltaJobStore:
    """Job-side store protocol: site_pages and web_corpus in Delta, workflow state in Lakebase, vectors via Direct Vector
    Access, the re-ask in-process (geologic.reask)."""

    def __init__(self, spark, conn, w):
        from geologic.config import settings as S
        self.spark, self.conn, self.w, self.S = spark, conn, w, S
        self._emb = None

    def _rows(self, sql):
        return [r.asDict(recursive=True) for r in self.spark.sql(sql).collect()]

    @property
    def embedder(self):
        if self._emb is None:
            from geologic.clients import Embedder
            self._emb = Embedder.from_workspace(self.w, self.S.embedding_endpoint)
        return self._emb

    def _lake(self, sql, args=()):
        self.conn.execute(sql, args)
        self.conn.commit()

    def current_epoch(self):
        return self.conn.execute("SELECT epoch FROM demo_state WHERE id = 1").fetchone()[0]

    def get_page(self, pid):
        if not _SAFE_ID.match(pid or ""):
            return None
        r = self._rows(f"SELECT * FROM {self.S.fq('site_pages')} WHERE page_id = '{pid}'")
        return r[0] if r else None

    def write_page(self, page):
        S, sp = self.S, self.spark
        sp.createDataFrame([page], sp.table(S.fq("site_pages")).schema).createOrReplaceTempView("new_page")
        sp.sql(f"MERGE INTO {S.fq('site_pages')} t USING new_page s ON t.page_id = s.page_id "
               "WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *")
        body = "concat(coalesce(s.body, ''), CASE WHEN s.jsonld IS NULL THEN '' ELSE concat(chr(10), s.jsonld) END)"
        sp.sql(f"""MERGE INTO {S.fq('web_corpus')} t USING new_page s ON t.doc_id = concat('lce_', s.page_id)
                   WHEN MATCHED THEN UPDATE SET t.body = {body}, t.last_updated = to_date(s.updated_at)
                   WHEN NOT MATCHED THEN INSERT (doc_id, source_type, publisher, title, body, published_at, is_official, page_id,
                                                 last_updated, domain, url, owner_class)
                   VALUES (concat('lce_', s.page_id), 'lce_page', 'littlecaesars.com', s.url, {body}, s.updated_at, true, s.page_id,
                           to_date(s.updated_at), 'littlecaesars.com', s.url, 'Owned')""")

    def record_version(self, page, by):
        self._lake("INSERT INTO cms_page_versions (page_id, version, body, jsonld, published_by) VALUES (%s,%s,%s,%s,%s) "
                   "ON CONFLICT DO NOTHING", (page["page_id"], page["version"], page.get("body"), page.get("jsonld"), by))

    def upsert_doc(self, doc):
        from geologic import vectors as V
        from geologic.clients import DvaRetriever
        V.upsert(self.w, self.S.sources_index, V.source_rows([doc], self.embedder.embed))
        wait_visible(DvaRetriever(self.w, self.S.sources_index, self.embedder), doc)

    def latest(self, prompt_ids):
        S, ids = self.S, _in_list(prompt_ids)
        if not ids:
            return {}
        from geologic.reask import answer_map
        answers = self._rows(f"SELECT r.*, p.prompt_text FROM {S.fq('v_latest_responses')} r JOIN {S.fq('prompts')} p "
                             f"USING (prompt_id) WHERE r.prompt_id IN ({ids})")
        claims = self._rows(f"SELECT * FROM {S.fq('v_latest_claims')} WHERE prompt_id IN ({ids})")
        return answer_map(answers, claims, {a["prompt_id"]: a["prompt_text"] for a in answers})

    def reask(self, prompt_ids):
        from datetime import date
        from geologic.clients import FmapiChat
        from geologic.probe.runner import ANSWER_SCHEMA, CLAIM_SCHEMA
        from geologic.reask import answer_map, make_context, make_engines, reask
        S, sp, ids = self.S, self.spark, _in_list(prompt_ids)
        if not ids:
            return {}
        prompts = self._rows(f"SELECT * FROM {S.fq('prompts')} WHERE prompt_id IN ({ids})")
        facts = self._rows(f"SELECT * FROM {S.fq('brand_facts')}")
        owned = [r["doc_id"] for r in self._rows(f"SELECT doc_id FROM {S.fq('web_corpus')} WHERE owner_class = 'Owned'")]
        epoch = sp.table(S.fq("probe_state")).first()["current_epoch"]
        chat = FmapiChat.from_workspace(self.w)
        engines = make_engines(self.w, chat, self.embedder, S.sources_index, S.engines)
        run, answers, claims = reask(prompts, engines, make_context(chat, S.judge_endpoint, facts, owned, date.today()), epoch, "publish")

        def write(rows, schema, table):
            cols = [c.split()[0] for c in schema.split(", ")]
            sp.createDataFrame([tuple(r[k] for k in cols) for r in rows], schema).write.mode("append").saveAsTable(S.fq(table))

        if answers:
            write(answers, ANSWER_SCHEMA, "probe_responses")
        if claims:
            write(claims, CLAIM_SCHEMA, "claims")
        write([run], "run_id STRING, epoch INT, run_type STRING, trigger STRING, prompt_ids ARRAY<STRING>, "
                     "started_at TIMESTAMP, finished_at TIMESTAMP, status STRING", "probe_runs")
        sp.sql(f"UPDATE {S.fq('probe_state')} SET latest_run_id = '{run['run_id']}' WHERE id = 1")
        return answer_map(answers, claims, {p["prompt_id"]: p["prompt_text"] for p in prompts})

    def save_results(self, rows):
        from geologic.results import UPSERT_RESULT, result_values
        for r in rows:
            self.conn.execute(UPSERT_RESULT, result_values(r))
        self.conn.commit()

    def set_state(self, fid, state, error=None):
        self._lake("UPDATE fixes SET state = %s, error = %s WHERE fix_id = %s AND state = 'publishing'", (state, error, fid))

    def set_step(self, fid, n):
        self._lake("UPDATE fixes SET publish_step = %s WHERE fix_id = %s", (n, fid))

    def audit(self, actor, action, ref, rule, point):
        self._lake("INSERT INTO audit_events (actor, action, object_ref, exclusion_rule_id, enforcement_point) "
                   "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING", (actor, action, ref, rule, point))


def baseline_source_sql(runs_table: str, base: str) -> str:
    """Run ids Reset copies: the baseline run plus later setup runs of the baseline run's own epoch."""
    return f"""(SELECT run_id FROM {runs_table} WHERE epoch = (SELECT epoch FROM {runs_table} WHERE run_id = '{base}') AND
               (run_id = '{base}' OR (trigger = 'setup' AND started_at >=
                    (SELECT started_at FROM {runs_table} WHERE run_id = '{base}'))))"""


_JSON_COLS = ("sentences", "checks")
_ARRAY_COLS = ("grounding_fact_ids", "prompt_ids")


def baseline_fix_row(row, epoch):
    """A fixes_baseline row (all strings, lists JSON-encoded) back into Lakebase values under the new epoch."""
    r = {k: v for k, v in row.items() if k != "created_at"}
    r["epoch"] = epoch
    for c in _ARRAY_COLS:
        if isinstance(r.get(c), str):
            r[c] = json.loads(r[c])
    for c in _JSON_COLS:
        if r.get(c) is not None and not isinstance(r[c], str):
            r[c] = json.dumps(r[c])
    return r


class DeltaResetStore:
    def __init__(self, spark, conn, w):
        from geologic.config import settings as S
        self.spark, self.conn, self.w, self.S = spark, conn, w, S
        self._job = DeltaJobStore(spark, conn, w)

    def _ids(self, sql):
        return {r[0] for r in self.spark.sql(sql).collect()}

    def bump_epoch(self):
        e = self.conn.execute("UPDATE demo_state SET epoch = epoch + 1 WHERE id = 1 RETURNING epoch").fetchone()[0]
        self.conn.commit()
        self.spark.sql(f"UPDATE {self.S.fq('probe_state')} SET current_epoch = {int(e)} WHERE id = 1")
        return e

    def restore_fixes(self, epoch):
        """Delete and re-insert in one transaction, so the app never sees an empty queue."""
        rows = [baseline_fix_row(r.asDict(), epoch) for r in self.spark.table(self.S.fq("fixes_baseline")).collect()]
        self.conn.execute("DELETE FROM fixes")
        for r in rows:
            cols = list(r)
            self.conn.execute(f"INSERT INTO fixes ({', '.join(cols)}) VALUES ({', '.join(['%s'] * len(cols))})", [r[c] for c in cols])
        self.conn.commit()

    def clear_page_versions(self):
        self.conn.execute("DELETE FROM cms_page_versions")
        self.conn.commit()

    def copy_baseline_probe(self, epoch):
        """The demo-start probe picture under the new epoch: the baseline run plus later setup runs of its epoch, ids suffixed
        _e{epoch}, original start times kept so the latest-response view resolves them in the same order."""
        S, e = self.S, int(epoch)
        base = self.spark.table(S.fq("probe_state")).first()["baseline_run_id"]
        if not _SAFE_ID.match(base or ""):
            raise RuntimeError(f"probe_state has no usable baseline_run_id: {base!r}")
        src = baseline_source_sql(S.fq("probe_runs"), base)
        sfx = f"'_e{e}'"
        self.spark.sql(f"""INSERT INTO {S.fq('probe_runs')} SELECT concat(run_id, {sfx}), {e}, run_type, 'reset', prompt_ids,
                           started_at, finished_at, status FROM {S.fq('probe_runs')} WHERE run_id IN {src}""")
        self.spark.sql(f"""INSERT INTO {S.fq('probe_responses')} SELECT concat(answer_id, {sfx}) AS answer_id,
                           concat(run_id, {sfx}) AS run_id, {e} AS epoch, * EXCEPT (answer_id, run_id, epoch)
                           FROM {S.fq('probe_responses')} WHERE run_id IN {src}""")
        self.spark.sql(f"""INSERT INTO {S.fq('claims')} SELECT concat(claim_id, {sfx}) AS claim_id, concat(answer_id, {sfx}) AS answer_id,
                           concat(run_id, {sfx}) AS run_id, {e} AS epoch, * EXCEPT (claim_id, answer_id, run_id, epoch)
                           FROM {S.fq('claims')} WHERE run_id IN {src}""")
        latest = self.spark.sql(f"SELECT run_id FROM {S.fq('probe_runs')} WHERE epoch = {e} AND trigger = 'reset' "
                                "ORDER BY started_at DESC LIMIT 1").first()["run_id"]
        self.spark.sql(f"UPDATE {S.fq('probe_state')} SET latest_run_id = '{latest}' WHERE id = 1")

    def restore_pages(self):
        S = self.S
        extra = self._ids(f"SELECT doc_id FROM {S.fq('web_corpus')}") - self._ids(f"SELECT doc_id FROM {S.fq('web_corpus_demo_start')}")
        self.spark.sql(f"INSERT OVERWRITE {S.fq('site_pages')} SELECT * FROM {S.fq('site_pages_demo_start')}")
        self.spark.sql(f"INSERT OVERWRITE {S.fq('web_corpus')} SELECT * FROM {S.fq('web_corpus_demo_start')}")
        return sorted(extra)

    def restore_source_vectors(self, extra_ids):
        from geologic import vectors as V
        docs = self._job._rows(f"SELECT * FROM {self.S.fq('web_corpus_demo_start')}")
        V.upsert(self.w, self.S.sources_index, V.source_rows(docs, self._job.embedder.embed))
        V.delete(self.w, self.S.sources_index, extra_ids)

    def restore_prompts(self):
        S = self.S
        extra = self._ids(f"SELECT prompt_id FROM {S.fq('prompts')}") - self._ids(f"SELECT prompt_id FROM {S.fq('prompts_demo_start')}")
        self.spark.sql(f"INSERT OVERWRITE {S.fq('prompts')} SELECT * FROM {S.fq('prompts_demo_start')}")
        self.spark.sql(f"INSERT OVERWRITE {S.fq('prompt_suggestions')} SELECT * FROM {S.fq('prompt_suggestions_demo_start')}")
        ids = _in_list(sorted(extra))
        if ids:   # Track and run adds 12 monthly volume rows per prompt
            self.spark.sql(f"DELETE FROM {S.fq('question_volume_monthly')} WHERE prompt_id IN ({ids})")
        return sorted(extra)

    def restore_prompt_vectors(self, extra_ids):
        from geologic import vectors as V
        S = self.S
        rows = V.prompt_rows(self._job._rows(f"SELECT * FROM {S.fq('prompts_demo_start')}"),
                             self._job._rows(f"SELECT * FROM {S.fq('prompt_suggestions_demo_start')}"), self._job.embedder.embed)
        V.upsert(self.w, S.prompt_index, rows)
        V.delete(self.w, S.prompt_index, extra_ids)
