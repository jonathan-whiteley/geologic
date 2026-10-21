import json
import sys
from types import SimpleNamespace as NS
import pytest
from geologic import vectors as V


class FakeIdx:
    def __init__(self): self.calls = []
    def upsert_data_vector_index(self, index_name, inputs_json):
        self.calls.append((index_name, json.loads(inputs_json)))
        return type("R", (), {"status": type("S", (), {"value": "SUCCESS"})()})()
    def delete_data_vector_index(self, index_name, primary_keys): self.calls.append(("delete", list(primary_keys)))


class W:
    def __init__(self): self.vector_search_indexes = FakeIdx()


def test_rows_and_upsert_batches():
    embed = lambda texts: [[float(len(t))] for t in texts]
    docs = [{"doc_id": f"d{i}", "title": "t", "body": "b" * i, "owner_class": "Owned", "domain": "littlecaesars.com"} for i in range(150)]
    rows = V.source_rows(docs, embed)
    assert rows[3]["embedding"] == [3.0] and set(rows[0]) == set(V.SOURCE_SCHEMA)
    w = W(); V.upsert(w, "idx", rows)
    assert [len(c[1]) for c in w.vector_search_indexes.calls] == [100, 50]


def test_prompt_rows_flag_suggestions():
    rows = V.prompt_rows([{"prompt_id": "q002", "prompt_text": "a", "cluster": "value"}],
                         [{"suggestion_id": "c001", "prompt_text": "b", "cluster": "value", "status": "suggested"},
                          {"suggestion_id": "c002", "prompt_text": "c", "cluster": "value", "status": "tracked"}],
                         lambda ts: [[0.0]] * len(ts))
    assert [(r["prompt_id"], r["kind"]) for r in rows] == [("q002", "tracked"), ("c001", "suggested")]
    assert set(rows[0]) == set(V.PROMPT_SCHEMA)


def test_upsert_failure_raises():
    class Bad(FakeIdx):
        def upsert_data_vector_index(self, index_name, inputs_json):
            return type("R", (), {"status": type("S", (), {"value": "PARTIAL_SUCCESS"})()})()
    w = W(); w.vector_search_indexes = Bad()
    with pytest.raises(RuntimeError):
        V.upsert(w, "idx", [{"doc_id": "x", "embedding": [0.0]}])


def test_delete_skips_empty_and_sends_one_key_per_call():
    # Live (story fixes 2): with SDK 0.114 a two-key delete_data_vector_index call removed only one row
    # (success_row_count 1); the second key needed its own call.
    w = W()
    V.delete(w, "idx", [])
    V.delete(w, "idx", (i for i in ["a", "b"]))
    assert w.vector_search_indexes.calls == [("delete", ["a"]), ("delete", ["b"])]


class Indexes:
    def __init__(self, exists, ready_after=0):
        self.exists, self.ready_after, self.created, self.gets = exists, ready_after, [], 0
    def get_index(self, name):
        self.gets += 1
        if not self.exists:
            from databricks.sdk.errors import NotFound
            raise NotFound("no index")
        return NS(status=NS(ready=self.gets > self.ready_after))
    def create_index(self, **kw):
        self.created.append(kw); self.exists = True


def _sdk_or_fakes(monkeypatch):
    """Use the real databricks-sdk when installed; otherwise install minimal stand-ins for the three classes
    ensure_direct_index imports (same keyword names as databricks-sdk 0.114) so the spec is still checked."""
    try:
        import databricks.sdk.errors, databricks.sdk.service.vectorsearch  # noqa: F401
        return
    except ImportError:
        pass
    import enum, types
    from dataclasses import dataclass

    class NotFound(Exception):
        pass

    class VectorIndexType(enum.Enum):
        DELTA_SYNC = "DELTA_SYNC"
        DIRECT_ACCESS = "DIRECT_ACCESS"

    @dataclass
    class EmbeddingVectorColumn:
        embedding_dimension: int | None = None
        name: str | None = None

    @dataclass
    class DirectAccessVectorIndexSpec:
        embedding_source_columns: list | None = None
        embedding_vector_columns: list | None = None
        schema_json: str | None = None

    mods = {n: types.ModuleType(n) for n in ("databricks", "databricks.sdk", "databricks.sdk.errors",
                                              "databricks.sdk.service", "databricks.sdk.service.vectorsearch")}
    mods["databricks.sdk.errors"].NotFound = NotFound
    vs = mods["databricks.sdk.service.vectorsearch"]
    vs.VectorIndexType, vs.EmbeddingVectorColumn, vs.DirectAccessVectorIndexSpec = (
        VectorIndexType, EmbeddingVectorColumn, DirectAccessVectorIndexSpec)
    for n, m in mods.items():
        monkeypatch.setitem(sys.modules, n, m)


def test_ensure_direct_index_creates_only_when_missing(monkeypatch):
    _sdk_or_fakes(monkeypatch)
    idx = Indexes(exists=False)
    assert V.ensure_direct_index(NS(vector_search_indexes=idx), "c.s.sources_idx", "geologic-vs", "doc_id", V.SOURCE_SCHEMA, 1024)
    kw = idx.created[0]
    assert kw["name"] == "c.s.sources_idx" and kw["endpoint_name"] == "geologic-vs" and kw["primary_key"] == "doc_id"
    assert kw["index_type"].value == "DIRECT_ACCESS"
    spec = kw["direct_access_index_spec"]
    assert json.loads(spec.schema_json) == V.SOURCE_SCHEMA
    assert [(c.name, c.embedding_dimension) for c in spec.embedding_vector_columns] == [("embedding", 1024)]
    assert not V.ensure_direct_index(NS(vector_search_indexes=idx), "c.s.sources_idx", "geologic-vs", "doc_id", V.SOURCE_SCHEMA, 1024)
    assert len(idx.created) == 1


def test_wait_ready(monkeypatch):
    monkeypatch.setattr(V.time, "sleep", lambda s: None)
    idx = Indexes(exists=True, ready_after=2)
    V.wait_ready(NS(vector_search_indexes=idx), "i")
    assert idx.gets == 3
    clock = iter(range(0, 10_000, 600))
    monkeypatch.setattr(V.time, "time", lambda: next(clock))
    with pytest.raises(TimeoutError):
        V.wait_ready(NS(vector_search_indexes=Indexes(exists=True, ready_after=99)), "i", timeout_s=1200)


# Ruling S2-A: Direct Vector Access scores hits by L2 distance, score = 1 / (1 + d^2). For unit vectors
# d^2 = 2 - 2 cos, so cos = 1 - d^2 / 2. vectors.query returns that cosine as "score".
def test_cosine_from_score_inverts_the_l2_score_for_unit_vectors():
    import math, random
    rnd = random.Random(7)
    for _ in range(20):
        a, b = ([rnd.uniform(-1, 1) for _ in range(16)] for _ in range(2))
        a, b = ([x / math.sqrt(sum(y * y for y in v)) for x in v] for v in (a, b))
        d2 = sum((x - y) ** 2 for x, y in zip(a, b))
        assert V.cosine_from_score(1 / (1 + d2)) == pytest.approx(sum(x * y for x, y in zip(a, b)), abs=1e-9)
    assert V.cosine_from_score(1.0) == 1.0 and V.cosine_from_score(0.2) == -1.0   # d^2 = 4: opposite vectors
    assert V.cosine_from_score(0.0) == -1.0 and V.cosine_from_score(None) == -1.0 and V.cosine_from_score("0.5") == 0.5


class QueryIdx:
    def __init__(self, cols, rows): self.cols, self.rows, self.calls = cols, rows, []
    def query_index(self, **kw):
        self.calls.append(kw)
        return NS(manifest=NS(columns=[NS(name=c) for c in self.cols]), result=NS(data_array=self.rows))


def test_query_by_vector_returns_rows_with_cosine_scores():
    idx = QueryIdx(["prompt_id", "kind", "score"], [["q202", "tracked", 0.5], ["s_x", "suggested", "0.25"]])
    rows = V.query(NS(vector_search_indexes=idx), "c.s.prompt_idx", ["prompt_id", "kind"], [0.6, 0.8], 5)
    assert idx.calls == [dict(index_name="c.s.prompt_idx", columns=["prompt_id", "kind"], query_vector=[0.6, 0.8], num_results=5)]
    assert rows == [{"prompt_id": "q202", "kind": "tracked", "score": 0.5}, {"prompt_id": "s_x", "kind": "suggested", "score": -0.5}]
    empty = NS(vector_search_indexes=NS(query_index=lambda **kw: NS(manifest=None, result=None)))
    assert V.query(empty, "i", ["prompt_id"], [1.0], 3) == []
    assert V.query(NS(vector_search_indexes=QueryIdx(["prompt_id", "score"], None)), "i", ["prompt_id"], [1.0], 3) == []



# Ruling S2-C (smoke 2 F-S2-2): vector_search prunes prompt_idx rows whose ids are in neither prompts nor prompt_suggestions.
class ScanIdx(FakeIdx):
    def __init__(self, pages):
        super().__init__(); self.pages, self.scans = pages, []
    def scan_index(self, index_name, last_primary_key=None, num_results=None):
        self.scans.append((index_name, last_primary_key, num_results))
        data = self.pages.get(last_primary_key, [])
        rows = [NS(fields=[NS(key="prompt_id", value=NS(string_value=i)), NS(key="kind", value=NS(string_value="x"))]) for i in data]
        return NS(data=rows, last_primary_key=data[-1] if data else None)


def test_index_ids_pages_through_scan():
    w = W(); w.vector_search_indexes = ScanIdx({None: ["q001", "q002"], "q002": ["s_a"], "s_a": []})
    assert V.index_ids(w, "idx", "prompt_id", page=2) == ["q001", "q002", "s_a"]
    assert [s[1] for s in w.vector_search_indexes.scans] == [None, "q002", "s_a"]


def test_prune_deletes_only_ids_not_kept():
    w = W(); w.vector_search_indexes = ScanIdx({None: ["q001", "s_old", "s_keep", "c004"]})
    gone = V.prune(w, "c.s.prompt_idx", "prompt_id", keep={"q001", "s_keep", "c004"})
    assert gone == ["s_old"] and w.vector_search_indexes.calls == [("delete", ["s_old"])]
    w3 = W(); w3.vector_search_indexes = ScanIdx({None: ["q001", "s_a", "s_b"]})
    assert V.prune(w3, "i", "prompt_id", keep={"q001"}) == ["s_a", "s_b"]
    assert w3.vector_search_indexes.calls == [("delete", ["s_a"]), ("delete", ["s_b"])]
    w2 = W(); w2.vector_search_indexes = ScanIdx({None: ["q001"]})
    assert V.prune(w2, "i", "prompt_id", keep={"q001"}) == [] and w2.vector_search_indexes.calls == []
