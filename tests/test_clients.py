# tests/test_clients.py
from types import SimpleNamespace as NS
from geologic.clients import DvaRetriever, Embedder, FmapiChat, PromptIndex, menu_match, menu_candidates

class FakeOpenAI:
    def __init__(self, content):
        self.chat = NS(completions=NS(create=lambda **kw: NS(choices=[NS(message=NS(content=content))])))

def test_chat_string_content():
    assert FmapiChat(FakeOpenAI("hi")).complete("ep", [{"role": "user", "content": "x"}]) == "hi"

def test_chat_list_content_joins_text_parts():
    parts = [{"type": "reasoning", "summary": []}, {"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    assert FmapiChat(FakeOpenAI(parts)).complete("ep", []) == "ab"

def test_chat_usage_context_sent_as_extra_body_only_when_given():
    seen = []
    def create(**kw):
        seen.append(kw)
        return NS(choices=[NS(message=NS(content="x"))])
    c = FmapiChat(NS(chat=NS(completions=NS(create=create))))
    c.complete("ep", [], usage_context={"app": "geologic"})
    c.complete("ep", [])
    assert seen[0]["extra_body"] == {"usage_context": {"app": "geologic"}}
    assert "extra_body" not in seen[1]

class FakeIndex:
    def __init__(self, cols, rows): self.cols, self.rows = cols, rows
    def similarity_search(self, **kw):
        return {"manifest": {"columns": [{"name": c} for c in self.cols]}, "result": {"data_array": self.rows}}

def test_menu_match_empty():
    assert menu_match(FakeIndex(["item_id", "search_text", "score"], []), "pizza") == (None, 0.0)

def test_menu_match_hit():
    idx = FakeIndex(["item_id", "search_text", "score"], [["detroit_pepperoni", "Detroit", 0.83]])
    assert menu_match(idx, "square pan pizza") == ("detroit_pepperoni", 0.83)


def test_menu_candidates_returns_triples():
    rows = [
        ["detroit_pepperoni", "square pan pizza thick crust", 0.72],
        ["thin_crust", "round pizza thin crust", 0.74],
        ["stuffed_crust", "round pizza stuffed crust", 0.71],
    ]
    idx = FakeIndex(["item_id", "search_text", "score"], rows)
    cands = menu_candidates(idx, "square pizza", k=3)
    assert len(cands) == 3
    assert cands[0] == ("detroit_pepperoni", "square pan pizza thick crust", 0.72)
    assert cands[1] == ("thin_crust", "round pizza thin crust", 0.74)


def test_menu_candidates_empty():
    assert menu_candidates(FakeIndex(["item_id", "search_text", "score"], []), "x") == []


class TempRejected(Exception):
    """Shape of openai.BadRequestError for models that only accept the default temperature."""


def test_chat_retries_without_temperature_when_model_rejects_it_and_remembers():
    seen = []
    def create(**kw):
        seen.append(kw)
        if "temperature" in kw:
            raise TempRejected("Error code: 400 - Model us.anthropic.claude-sonnet-5-5 does not support the temperature parameter.")
        return NS(choices=[NS(message=NS(content="ok"))])
    c = FmapiChat(NS(chat=NS(completions=NS(create=create))))
    assert c.complete("ep", []) == "ok"
    assert c.complete("ep", []) == "ok"
    assert [("temperature" in kw) for kw in seen] == [True, False, False]  # second call skips the doomed attempt


def test_chat_other_errors_still_raise():
    def create(**kw):
        raise TempRejected("Error code: 429 - rate limited")
    c = FmapiChat(NS(chat=NS(completions=NS(create=create))))
    try:
        c.complete("ep", [])
        assert False, "expected raise"
    except TempRejected:
        pass


class FakeEmbeddings:
    def __init__(self): self.calls = []
    def create(self, model, input):
        self.calls.append((model, list(input)))
        # out of order on purpose: the embedder must reorder by index
        return NS(data=[NS(index=i, embedding=[float(len(t))]) for i, t in reversed(list(enumerate(input)))])


def test_embedder_batches():
    fake = NS(embeddings=FakeEmbeddings())
    texts = [f"t{'x' * i}" for i in range(20)]
    vecs = Embedder(fake, "databricks-gte-large-en", batch=16).embed(texts)
    assert [len(b) for _, b in fake.embeddings.calls] == [16, 4]
    assert {m for m, _ in fake.embeddings.calls} == {"databricks-gte-large-en"}
    assert vecs == [[float(len(t))] for t in texts]
    assert Embedder(fake, "ep").embed([]) == []


def test_embedder_from_workspace():
    oa = NS(embeddings=FakeEmbeddings())
    e = Embedder.from_workspace(NS(serving_endpoints=NS(get_open_ai_client=lambda: oa)), "ep")
    assert e.endpoint == "ep" and e.embed(["a"]) == [[1.0]]


class FakeVsIndexes:
    def __init__(self, cols, rows): self.cols, self.rows, self.calls = cols, rows, []
    def query_index(self, **kw):
        self.calls.append(kw)
        return NS(manifest=NS(columns=[NS(name=c) for c in self.cols]), result=NS(data_array=self.rows))


class FixedEmbedder:
    def __init__(self): self.seen = []
    def embed(self, texts):
        self.seen += list(texts)
        return [[0.5, 0.25] for _ in texts]


def test_dva_retriever_queries_by_vector():
    idx = FakeVsIndexes(["doc_id", "title", "body", "owner_class", "score"],
                        [["lce_pg_deals", "Deals", "$4.99", "Owned", 0.9], ["comp_x", "Dominos", "$7.99", "Competitor", 0.7]])
    emb = FixedEmbedder()
    docs = DvaRetriever(NS(vector_search_indexes=idx), "jdub_demo.geologic_v3.sources_idx", emb).search("deals", 3)
    kw = idx.calls[0]
    assert kw["query_vector"] == [0.5, 0.25] and "query_text" not in kw and kw["num_results"] == 3
    assert kw["index_name"] == "jdub_demo.geologic_v3.sources_idx" and kw["columns"] == ["doc_id", "title", "body", "owner_class"]
    assert [(d.doc_id, d.is_official) for d in docs] == [("lce_pg_deals", True), ("comp_x", False)]
    assert docs[0].body == "$4.99" and emb.seen == ["deals"]


def test_dva_retriever_empty_result():
    idx = FakeVsIndexes(["doc_id", "title", "body", "owner_class", "score"], None)
    assert DvaRetriever(NS(vector_search_indexes=idx), "i", FixedEmbedder()).search("x", 3) == []
    idx2 = NS(query_index=lambda **kw: NS(manifest=None, result=None))
    assert DvaRetriever(NS(vector_search_indexes=idx2), "i", FixedEmbedder()).search("x", 3) == []


def test_prompt_index_nearest():
    idx = FakeVsIndexes(["prompt_id", "prompt_text", "kind", "cluster", "score"],
                        [["q201", "Super Bowl party for 12", "tracked", "game_day_party", "0.91"],
                         ["c004", "party pizza", "suggested", "game_day_party", 0.82]])
    out = PromptIndex(NS(vector_search_indexes=idx), "jdub_demo.geologic_v3.prompt_idx", FixedEmbedder()).nearest("party")
    kw = idx.calls[0]
    assert kw["columns"] == ["prompt_id", "prompt_text", "kind", "cluster"] and kw["num_results"] == 3
    assert "query_vector" in kw and "query_text" not in kw
    assert out == [{"id": "q201", "prompt_text": "Super Bowl party for 12", "kind": "tracked", "cluster": "game_day_party", "score": 0.91},
                   {"id": "c004", "prompt_text": "party pizza", "kind": "suggested", "cluster": "game_day_party", "score": 0.82}]
    assert all(isinstance(r["score"], float) for r in out)
