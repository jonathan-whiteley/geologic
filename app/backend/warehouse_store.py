"""The publish store protocol (geologic.publish_flow) for the app: pages, corpus and probe rows through the SQL warehouse
with :named parameters, workflow state through Lakebase (FixRepo), vectors through Direct Vector Access."""
import json
import re
from datetime import date, datetime
from geologic import vectors as V
from geologic.config import settings as S
from geologic.publish_flow import wait_visible

_SAFE_ID = re.compile(r"^[A-Za-z0-9_]+$")
ANSWER_ARRAYS = {"retrieved_doc_ids", "cited_doc_ids", "brands_mentioned"}


def _iso(v):
    return v.isoformat() if isinstance(v, (datetime, date)) else v


def insert_rows(table, rows, array_cols, ts_cols=()):
    """INSERT for rows of dicts. Columns from the first row, params named r{i}_{col}; arrays go as JSON through
    from_json(:p, 'array<string>'), timestamps as ISO strings through to_timestamp(:p)."""
    cols = list(rows[0])
    params, values = {}, []
    for i, r in enumerate(rows):
        exprs = []
        for c in cols:
            p = f"r{i}_{c}"
            if c in array_cols:
                params[p] = json.dumps(list(r.get(c) or []))
                exprs.append(f"from_json(:{p}, 'array<string>')")
            elif c in ts_cols:
                params[p] = _iso(r.get(c))
                exprs.append(f"to_timestamp(:{p})")
            else:
                params[p] = r.get(c)
                exprs.append(f":{p}")
        values.append(f"({', '.join(exprs)})")
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES {', '.join(values)}", params


MAX_PARAMS = 250   # stay under the per-statement parameter cap


def insert_batches(table, rows, array_cols, ts_cols=()):
    """insert_rows in chunks so no statement carries more than MAX_PARAMS parameters."""
    if not rows:
        return []
    per = max(1, MAX_PARAMS // max(1, len(rows[0])))
    return [insert_rows(table, rows[i:i + per], array_cols, ts_cols) for i in range(0, len(rows), per)]


UI_ONLY = {"cited"}   # doc chips attached for Track and run responses; probe_responses has no such column


def response_rows(answers):
    return [{k: v for k, v in a.items() if k not in UI_ONLY} for a in answers]


def _in_list(ids):
    ok = [i for i in ids or [] if isinstance(i, str) and _SAFE_ID.match(i)]
    return ",".join(f"'{i}'" for i in ok) or None


def _day(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, str):
        return date.fromisoformat(v[:10])
    return v


def parse_facts(rows):
    return [{**f, "valid_from": _day(f["valid_from"]), "valid_to": _day(f.get("valid_to"))} for f in rows]


class WarehouseStore:
    def __init__(self, repo, w, trigger="approve", query=None):
        if query is None:
            from backend.warehouse import query
        self.repo, self.w, self.trigger, self.q = repo, w, trigger, query
        self._emb = None

    @property
    def embedder(self):
        if self._emb is None:
            from geologic.clients import Embedder
            self._emb = Embedder.from_workspace(self.w, S.embedding_endpoint)
        return self._emb

    # Lakebase half
    def current_epoch(self):
        return self.repo.epoch()

    def record_version(self, page, by):
        self.repo.record_version(page, by)

    def set_state(self, fix_id, state, error=None):
        self.repo.set_state(fix_id, state, error)

    def set_step(self, fix_id, n):
        self.repo.set_step(fix_id, n)

    def audit(self, actor, action, ref, rule, point):
        self.repo.audit(actor, action, ref, rule, point)

    def save_results(self, rows):
        self.repo.save_results(rows)

    # Warehouse half
    def get_page(self, page_id):
        if not _SAFE_ID.match(page_id or ""):
            return None
        r = self.q(f"SELECT * FROM {S.fq('site_pages')} WHERE page_id = :p", {"p": page_id})
        return r[0] if r else None

    def write_page(self, page):
        p = {"page_id": page["page_id"], "url": page["url"], "page_type": page.get("page_type"),
             "primary_item_id": page.get("primary_item_id"), "body": page.get("body"), "jsonld": page.get("jsonld"),
             "has_valid_jsonld": bool(page.get("has_valid_jsonld")), "version": int(page.get("version") or 0),
             "updated_at": _iso(page.get("updated_at")), "primary_subject": page.get("primary_subject")}
        s = lambda k: f"CAST(:{k} AS STRING) AS {k}"
        src = (f"SELECT {s('page_id')}, {s('url')}, {s('page_type')}, {s('primary_item_id')}, {s('body')}, {s('jsonld')}, "
               "CAST(:has_valid_jsonld AS BOOLEAN) AS has_valid_jsonld, CAST(:version AS BIGINT) AS version, "
               f"to_timestamp(:updated_at) AS updated_at, {s('primary_subject')}")
        self.q(f"MERGE INTO {S.fq('site_pages')} t USING ({src}) s ON t.page_id = s.page_id "
               "WHEN MATCHED THEN UPDATE SET * WHEN NOT MATCHED THEN INSERT *", p)
        body = "concat(coalesce(s.body, ''), CASE WHEN s.jsonld IS NULL THEN '' ELSE concat(chr(10), s.jsonld) END)"
        self.q(f"""MERGE INTO {S.fq('web_corpus')} t USING ({src}) s ON t.doc_id = concat('lce_', s.page_id)
                   WHEN MATCHED THEN UPDATE SET t.body = {body}, t.last_updated = to_date(s.updated_at)
                   WHEN NOT MATCHED THEN INSERT (doc_id, source_type, publisher, title, body, published_at, is_official, page_id,
                                                 last_updated, domain, url, owner_class)
                   VALUES (concat('lce_', s.page_id), 'lce_page', 'littlecaesars.com', s.url, {body}, s.updated_at, true, s.page_id,
                           to_date(s.updated_at), 'littlecaesars.com', s.url, 'Owned')""", p)

    def upsert_doc(self, doc):
        from geologic.clients import DvaRetriever
        V.upsert(self.w, S.sources_index, V.source_rows([doc], self.embedder.embed))
        wait_visible(DvaRetriever(self.w, S.sources_index, self.embedder), doc)

    def _chips(self, answers):
        ids = _in_list(sorted({d for a in answers for d in a.get("cited_doc_ids") or []}))
        docs = {d["doc_id"]: d for d in self.q(f"SELECT doc_id, domain, owner_class, title, url, last_updated FROM "
                                                f"{S.fq('web_corpus')} WHERE doc_id IN ({ids})")} if ids else {}
        for a in answers:
            a["cited"] = [docs.get(d) or {"doc_id": d, "domain": None, "owner_class": None, "title": d, "url": None,
                                          "last_updated": None} for d in a.get("cited_doc_ids") or []]

    def latest(self, prompt_ids):
        from geologic.reask import answer_map
        ids = _in_list(prompt_ids)
        if not ids:
            return {}
        answers = self.q(f"SELECT r.*, p.prompt_text FROM {S.fq('v_latest_responses')} r JOIN {S.fq('prompts')} p "
                         f"USING (prompt_id) WHERE r.prompt_id IN ({ids})")
        claims = self.q(f"SELECT * FROM {S.fq('v_latest_claims')} WHERE prompt_id IN ({ids})")
        return answer_map(answers, claims, {a["prompt_id"]: a["prompt_text"] for a in answers})

    def reask(self, prompt_ids, epoch=None):
        """Re-ask under `epoch` (the fix's epoch; the current epoch for Track and run). If a Reset moved the epoch while the
        engines answered, nothing is written."""
        from geologic.clients import FmapiChat
        from geologic.reask import answer_map, make_context, make_engines, reask
        ids = _in_list(prompt_ids)
        if not ids:
            return {}
        prompts = self.q(f"SELECT prompt_id, prompt_text FROM {S.fq('prompts')} WHERE prompt_id IN ({ids})")
        facts = parse_facts(self.q(f"SELECT * FROM {S.fq('brand_facts')}"))
        owned = [r["doc_id"] for r in self.q(f"SELECT doc_id FROM {S.fq('web_corpus')} WHERE owner_class = 'Owned'")]
        chat = FmapiChat.from_workspace(self.w)
        engines = make_engines(self.w, chat, self.embedder, S.sources_index, S.engines)
        epoch = self.repo.epoch() if epoch is None else epoch
        run, answers, claims = reask(prompts, engines, make_context(chat, S.judge_endpoint, facts, owned, date.today()),
                                     epoch, self.trigger)
        self._chips(answers)
        texts = {p["prompt_id"]: p["prompt_text"] for p in prompts}
        if self.repo.epoch() != epoch:
            print(f"re-ask {run['run_id']}: epoch moved from {epoch}; results not written")
            return answer_map(answers, claims, texts)
        for sql, params in (insert_batches(S.fq("probe_responses"), response_rows(answers), ANSWER_ARRAYS)
                            + insert_batches(S.fq("claims"), claims, set())
                            + insert_batches(S.fq("probe_runs"), [run], {"prompt_ids"}, ts_cols={"started_at", "finished_at"})):
            self.q(sql, params)
        self.q(f"UPDATE {S.fq('probe_state')} SET latest_run_id = :r WHERE id = 1", {"r": run["run_id"]})
        return answer_map(answers, claims, texts)
