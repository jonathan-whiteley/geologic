# tests/test_clients.py
from types import SimpleNamespace as NS
from geologic.clients import FmapiChat, VsRetriever, menu_match

class FakeOpenAI:
    def __init__(self, content):
        self.chat = NS(completions=NS(create=lambda **kw: NS(choices=[NS(message=NS(content=content))])))

def test_chat_string_content():
    assert FmapiChat(FakeOpenAI("hi")).complete("ep", [{"role": "user", "content": "x"}]) == "hi"

def test_chat_list_content_joins_text_parts():
    parts = [{"type": "reasoning", "summary": []}, {"type": "text", "text": "a"}, {"type": "text", "text": "b"}]
    assert FmapiChat(FakeOpenAI(parts)).complete("ep", []) == "ab"

class FakeIndex:
    def __init__(self, cols, rows): self.cols, self.rows = cols, rows
    def similarity_search(self, **kw):
        return {"manifest": {"columns": [{"name": c} for c in self.cols]}, "result": {"data_array": self.rows}}

def test_retriever_maps_rows():
    idx = FakeIndex(["doc_id", "title", "body", "is_official", "score"], [["lce_pg_deals", "Deals", "$4.99", True, 0.9]])
    docs = VsRetriever(idx).search("deals", 3)
    assert docs[0].doc_id == "lce_pg_deals" and docs[0].is_official is True

def test_menu_match_empty():
    assert menu_match(FakeIndex(["item_id", "search_text", "score"], []), "pizza") == (None, 0.0)

def test_menu_match_hit():
    idx = FakeIndex(["item_id", "search_text", "score"], [["detroit_pepperoni", "Detroit", 0.83]])
    assert menu_match(idx, "square pan pizza") == ("detroit_pepperoni", 0.83)
