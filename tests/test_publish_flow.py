from datetime import datetime, timezone
from geologic.datagen.reference import exclusion_rules
from geologic.publish_flow import publish_fix, publish_batch, reset, FRIENDLY_ERROR, baseline_fix_row

NOW = datetime(2026, 10, 22, tzinfo=timezone.utc)
RULES = exclusion_rules()

class Store:
    def __init__(self, epoch=1, engines=("Claude", "ChatGPT", "Gemini", "Meta AI"), fail_reask=False):
        self.epoch, self.engines, self.fail_reask = epoch, engines, fail_reask
        self.pages = {"pg_deals_game_day": {"page_id": "pg_deals_game_day", "url": "u", "body": "## Game Day Deals\nx", "jsonld": None, "version": 1}}
        self.states, self.steps, self.audits, self.docs, self.versions, self.results, self.reasked = {}, [], [], [], [], [], []
        self.reask_epochs = []
    def current_epoch(self): return self.epoch
    def get_page(self, pid): return dict(self.pages[pid]) if pid in self.pages else None
    def write_page(self, p): self.pages[p["page_id"]] = p
    def record_version(self, p, by): self.versions.append((p["page_id"], p["version"], by))
    def upsert_doc(self, d): self.docs.append(d)
    def latest(self, pids): return {(p, e): {"answer": {"engine": e, "prompt_id": p, "status": "ok", "lce_mentioned": False, "lce_rank": None,
                                                         "cited_doc_ids": [], "retrieved_doc_ids": [], "answer": "b"}, "claims": []}
                                    for p in pids for e in self.engines}
    def reask(self, pids, epoch=None):
        self.reasked.append(list(pids)); self.reask_epochs.append(epoch)
        if self.fail_reask: raise RuntimeError("gateway down")
        out = {}
        for p in pids:
            for e in self.engines:
                st = "engine_error" if e == "Meta AI" else "ok"
                out[(p, e)] = {"answer": {"engine": e, "prompt_id": p, "status": st, "lce_mentioned": st == "ok", "lce_rank": 1,
                                          "cited_doc_ids": ["lce_pg_deals_game_day"], "retrieved_doc_ids": ["lce_pg_deals_game_day"],
                                          "answer": "a"}, "claims": []}
        return out
    def save_results(self, rows): self.results += rows
    def set_state(self, fid, state, error=None):
        if self.states.get(fid, ("publishing",))[0] == "publishing": self.states[fid] = (state, error)
    def set_step(self, fid, n): self.steps.append(n)
    def audit(self, *a): self.audits.append(a)

FIX = {"fix_id": "fx_1", "epoch": 1, "issue_id": "is_1", "title": "t", "tier": "T1", "asset_type": "owned_patch", "page_id": "pg_deals_game_day",
       "section_id": "game-day-deals", "op": "insert", "patch_text": "## Feeding 12\nThe Party Pack feeds 12 for $29.99.",
       "persona_id": None, "prompt_ids": ["q201"], "reviewer": "r"}

def test_publish_fix_happy_path():
    st = Store()
    assert publish_fix(FIX, st, RULES, now=NOW) == "published"
    assert st.steps == [1, 2, 3, 4, 5] and st.states["fx_1"][0] == "published"
    assert "## Feeding 12" in st.pages["pg_deals_game_day"]["body"] and st.versions == [("pg_deals_game_day", 2, "fx_1")]
    assert [d["doc_id"] for d in st.docs] == ["lce_pg_deals_game_day"] and st.docs[0]["owner_class"] == "Owned"
    assert st.reasked == [["q201"]] and len(st.results) == 4

def test_publish_fix_partial_engine_failure():  # Review Focus 1
    st = Store()
    assert publish_fix(FIX, st, RULES, now=NOW) == "published"
    assert {r["engine"]: r["status"] for r in st.results}["Meta AI"] == "engine_error"

def test_publish_fix_reask_exception_releases_with_friendly_error():
    st = Store(fail_reask=True)
    assert publish_fix(FIX, st, RULES, now=NOW) == "failed"
    assert st.states["fx_1"] == ("pending_review", FRIENDLY_ERROR) and st.audits[-1][1] == "failed" and st.results == []

def test_publish_fix_stale_epoch():  # Review Focus 3
    st = Store(epoch=2)
    assert publish_fix(FIX, st, RULES, now=NOW) == "stale" and st.pages["pg_deals_game_day"]["version"] == 1

def test_policy_recheck_blocks_gambling_text():
    st = Store()
    bet = {**FIX, "patch_text": "Same-game parlay tonight. Gambling problem? Call 1-800-GAMBLER."}
    assert publish_fix(bet, st, RULES, now=NOW) == "blocked" and st.audits[-1][3:] == ("EX-03", "publish") and st.docs == []

def test_retry_after_failed_reask_does_not_patch_twice():  # Review Focus 1: "Publish failed. Try again." then Approve again
    st = Store(fail_reask=True)
    assert publish_fix(FIX, st, RULES, now=NOW) == "failed"
    st.fail_reask, st.states = False, {}            # the app re-claims the row (state publishing) and approves again
    assert publish_fix(FIX, st, RULES, now=NOW) == "published"
    assert st.pages["pg_deals_game_day"]["body"].count("## Feeding 12") == 1 and st.versions == [("pg_deals_game_day", 2, "fx_1")]
    assert len(st.docs) == 2 and st.reasked == [["q201"], ["q201"]] and len(st.results) == 4

def test_retry_of_jsonld_fix_is_idempotent():
    st = Store()
    j = {**FIX, "asset_type": "jsonld", "section_id": "jsonld", "op": "replace", "patch_text": '{"@type":"Organization"}'}
    st.pages["pg_deals_game_day"]["jsonld"] = j["patch_text"]
    assert publish_fix(j, st, RULES, now=NOW) == "published" and st.versions == [] and len(st.docs) == 1

def test_external_lane_is_approved_without_page_change():
    st = Store()
    email = {**FIX, "asset_type": "correction_email", "page_id": None, "section_id": "email"}
    assert publish_fix(email, st, RULES, now=NOW) == "approved" and st.docs == [] and st.reasked == []

def test_new_answer_page_is_created():
    st = Store()
    page = {**FIX, "asset_type": "answer_page", "page_id": "pg_answer_q115", "section_id": "main", "op": "insert",
            "patch_text": "## Which chain has the best breadsticks?\nCrazy Bread is $3.99.", "prompt_ids": ["q115"]}
    assert publish_fix(page, st, RULES, now=NOW) == "published"
    assert st.pages["pg_answer_q115"]["url"] == "https://littlecaesars.com/answers/answer-q115" and st.pages["pg_answer_q115"]["version"] == 1

def test_batch_reasks_once_for_the_union_of_prompts():
    st = Store()
    a = {**FIX, "fix_id": "fx_a", "asset_type": "jsonld", "section_id": "jsonld", "op": "replace", "patch_text": '{"@type":"Organization"}', "prompt_ids": ["q142"]}
    b = {**a, "fix_id": "fx_b", "prompt_ids": ["q142", "q002"]}
    assert publish_batch([a, b], st, RULES, now=NOW) == {"fx_a": "published", "fx_b": "published"}
    assert st.reasked == [["q002", "q142"]] and st.pages["pg_deals_game_day"]["jsonld"] == '{"@type":"Organization"}'

def test_batch_reask_failure_releases_every_fix():
    st = Store(fail_reask=True)
    a = {**FIX, "fix_id": "fx_a", "asset_type": "jsonld", "section_id": "jsonld", "op": "replace", "patch_text": '{"@type":"Organization"}'}
    assert publish_batch([a, {**a, "fix_id": "fx_b"}], st, RULES, now=NOW) == {"fx_a": "failed", "fx_b": "failed"}
    assert st.states["fx_a"] == ("pending_review", FRIENDLY_ERROR) and st.states["fx_b"] == ("pending_review", FRIENDLY_ERROR)

class ResetStore:
    def __init__(self): self.calls = []
    def __getattr__(self, name):
        def f(*a):
            self.calls.append(name)
            return {"bump_epoch": 5, "restore_pages": ["lce_pg_answer_q115"], "restore_prompts": ["q301"]}.get(name)
        return f

def test_reset_order_and_never_touches_results():
    st = ResetStore()
    assert reset(st) == 5
    assert st.calls == ["bump_epoch", "restore_fixes", "clear_page_versions", "copy_baseline_probe", "restore_pages",
                        "restore_source_vectors", "restore_prompts", "restore_prompt_vectors"]

def test_baseline_row_reparses_lists_under_the_new_epoch():
    r = baseline_fix_row({"fix_id": "fx_1", "epoch": 1, "prompt_ids": '["q201"]', "grounding_fact_ids": '["F12"]',
                          "checks": '[{"key": "grounded"}]', "sentences": "[]", "created_at": "t"}, 7)
    assert r["epoch"] == 7 and r["prompt_ids"] == ["q201"] and r["grounding_fact_ids"] == ["F12"] and "created_at" not in r
    assert r["checks"] == '[{"key": "grounded"}]'


def test_reask_runs_under_the_fix_epoch():   # fix round 1: probe rows are written under the fix's epoch
    st = Store()
    publish_fix(FIX, st, RULES, now=NOW)
    a = {**FIX, "fix_id": "fx_a", "asset_type": "jsonld", "section_id": "jsonld", "op": "replace", "patch_text": '{"@type":"Organization"}'}
    publish_batch([a], st, RULES, now=NOW)
    assert st.reask_epochs == [1, 1]


class _Row(dict):
    def asDict(self, recursive=False): return dict(self)


class _Spark:
    def __init__(self, tables): self.tables = tables
    def sql(self, q):
        rows = next(v for k, v in self.tables.items() if q.rstrip().endswith("." + k))
        return type("DF", (), {"collect": lambda _s: [_Row(r) for r in rows]})()


class _Idx:
    """Direct Vector Access fake: upserts add keys, scan pages them, delete removes one key per call."""
    def __init__(self, keys): self.keys, self.deletes = {i: set(k) for i, k in keys.items()}, []
    def upsert_data_vector_index(self, index_name, inputs_json):
        import json
        pk = "doc_id" if index_name.endswith("sources_idx") else "prompt_id"
        self.keys[index_name] |= {r[pk] for r in json.loads(inputs_json)}
        return type("R", (), {"status": type("S", (), {"value": "SUCCESS"})()})()
    def scan_index(self, index_name, last_primary_key=None, num_results=None):
        from types import SimpleNamespace as N
        pk = "doc_id" if index_name.endswith("sources_idx") else "prompt_id"
        ids = sorted(self.keys[index_name]) if last_primary_key is None else []
        return N(data=[N(fields=[N(key=pk, value=N(string_value=i))]) for i in ids], last_primary_key=ids[-1] if ids else None)
    def delete_data_vector_index(self, index_name, primary_keys):
        assert len(primary_keys) == 1   # one key per call (sdk multi-key delete removes only one row)
        self.deletes.append((index_name, primary_keys[0])); self.keys[index_name].discard(primary_keys[0])


def _reset_store(idx, tables):
    from types import SimpleNamespace as N
    from geologic.publish_flow import DeltaResetStore
    st = DeltaResetStore(_Spark(tables), conn=None, w=N(vector_search_indexes=idx))
    st._job._emb = N(embed=lambda texts: [[1.0, 0.0]] * len(texts))
    return st


def test_reset_prunes_both_vector_indexes_to_the_demo_start_ids():   # final review M1
    from geologic.config import settings as S
    doc = {"doc_id": "lce_pg_menu", "title": "t", "body": "b", "owner_class": "Owned", "domain": "littlecaesars.com"}
    tables = {"web_corpus_demo_start": [doc],
              "prompts_demo_start": [{"prompt_id": "q201", "prompt_text": "p", "cluster": "game_day_party"}],
              "prompt_suggestions_demo_start": [{"suggestion_id": "c004", "prompt_text": "s", "cluster": "value", "status": "suggested"},
                                                {"suggestion_id": "c009", "prompt_text": "s", "cluster": "value", "status": "tracked"}]}
    # Orphans the table diff never sees: a page vector whose corpus row was never written, a tracked prompt vector, and a
    # vector for a suggestion that is no longer 'suggested' at demo start.
    idx = _Idx({S.sources_index: {"lce_pg_menu", "lce_pg_answer_q115", "lce_pg_orphan"},
                S.prompt_index: {"q201", "q301", "q302", "c009"}})
    st = _reset_store(idx, tables)
    st.restore_source_vectors(["lce_pg_answer_q115"])
    st.restore_prompt_vectors(["q301"])
    assert idx.keys[S.sources_index] == {"lce_pg_menu"} and idx.keys[S.prompt_index] == {"q201", "c004"}
    assert sorted(i for _, i in idx.deletes) == ["c009", "lce_pg_answer_q115", "lce_pg_orphan", "q301", "q302"]
