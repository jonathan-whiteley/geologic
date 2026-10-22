from geologic.probe.engine import Doc, EngineProxy

class FakeRetriever:
    def search(self, q, k):
        return [Doc("lce_pg_deals", "Deals", "$4.99 online", True), Doc("blog_x", "Blog", "$5 pizza", False)]

class FakeChat:
    def __init__(self, reply): self.reply, self.calls, self.kwargs = reply, [], []
    def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
        self.calls.append((endpoint, messages)); self.kwargs.append({"usage_context": usage_context}); return self.reply

def test_citations_filtered_to_retrieved():
    chat = FakeChat("It is $5 [blog_x]. See also [made_up_id] and [lce_pg_deals].")
    a = EngineProxy("Claude", "ep", FakeRetriever(), chat).answer("price?")
    assert a.cited_doc_ids == ["blog_x", "lce_pg_deals"]
    assert "blog_x" in chat.calls[0][1][-1]["content"]      # sources are in the prompt

def test_no_citations():
    a = EngineProxy("Claude", "ep", FakeRetriever(), FakeChat("No idea.")).answer("price?")
    assert a.cited_doc_ids == []

def test_engine_call_carries_usage_context():
    chat = FakeChat("ok")
    EngineProxy("Claude", "ep", FakeRetriever(), chat).answer("price?")
    assert chat.kwargs[0]["usage_context"] == {"app": "geologic_v3", "role": "probe"}

def test_usage_context_follows_schema(monkeypatch):
    import geologic.probe.engine as E
    from geologic.config import Settings
    monkeypatch.setattr(E, "settings", Settings(schema="geologic_v3"))
    assert E.usage_context() == {"app": "geologic_v3", "role": "probe"}

def test_answer_keeps_retrieved_docs():
    r = FakeRetriever()
    a = EngineProxy("Claude", "ep", r, FakeChat("It is $5 [blog_x].")).answer("price?")
    assert a.retrieved_doc_ids == ["lce_pg_deals", "blog_x"]
    assert a.docs == tuple(r.search("price?", 6)) and isinstance(a.docs, tuple)
