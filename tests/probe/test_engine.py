from geologic.probe.engine import Doc, EngineProxy

class FakeRetriever:
    def search(self, q, k):
        return [Doc("lce_pg_deals", "Deals", "$4.99 online", True), Doc("blog_x", "Blog", "$5 pizza", False)]

class FakeChat:
    def __init__(self, reply): self.reply, self.calls = reply, []
    def complete(self, endpoint, messages, max_tokens=600):
        self.calls.append((endpoint, messages)); return self.reply

def test_citations_filtered_to_retrieved():
    chat = FakeChat("It is $5 [blog_x]. See also [made_up_id] and [lce_pg_deals].")
    a = EngineProxy("Claude", "ep", FakeRetriever(), chat).answer("price?")
    assert a.cited_doc_ids == ["blog_x", "lce_pg_deals"]
    assert "blog_x" in chat.calls[0][1][-1]["content"]      # sources are in the prompt

def test_no_citations():
    a = EngineProxy("Claude", "ep", FakeRetriever(), FakeChat("No idea.")).answer("price?")
    assert a.cited_doc_ids == []
