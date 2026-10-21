import json
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


def test_delete_skips_empty_and_passes_ids():
    w = W()
    V.delete(w, "idx", [])
    V.delete(w, "idx", (i for i in ["a", "b"]))
    assert w.vector_search_indexes.calls == [("delete", ["a", "b"])]


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


def test_ensure_direct_index_creates_only_when_missing():
    pytest.importorskip("databricks.sdk")
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
