"""Adapters from Databricks services to the core protocols. Kept thin so the core stays testable."""
from __future__ import annotations
from geologic.probe.engine import Doc


class FmapiChat:
    def __init__(self, openai_client):
        self._c = openai_client

    @classmethod
    def from_workspace(cls, w):
        return cls(w.serving_endpoints.get_open_ai_client())

    def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
        kw = {"extra_body": {"usage_context": usage_context}} if usage_context else {}
        r = self._c.chat.completions.create(model=endpoint, messages=messages, max_tokens=max_tokens, temperature=0.2, **kw)
        content = r.choices[0].message.content
        if isinstance(content, list):  # reasoning models return typed parts
            return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
        return content or ""


def _rows(res):
    cols = [c["name"] for c in res["manifest"]["columns"]]
    return [dict(zip(cols, r)) for r in res.get("result", {}).get("data_array", []) or []]


class VsRetriever:
    def __init__(self, index, columns=("doc_id", "title", "body", "is_official")):
        self.index, self.columns = index, list(columns)

    def search(self, query, k):
        res = self.index.similarity_search(query_text=query, columns=self.columns, num_results=k)
        return [Doc(r["doc_id"], r["title"], r["body"], bool(r["is_official"])) for r in _rows(res)]


def menu_match(index, text):
    rows = _rows(index.similarity_search(query_text=text, columns=["item_id", "search_text"], num_results=1))
    return (rows[0]["item_id"], float(rows[0]["score"])) if rows else (None, 0.0)


def menu_candidates(index, text, k=5) -> list[tuple[str, str, float]]:
    """Return top-k (item_id, search_text, score) candidates for reranking.

    Note: 'score' is auto-returned by VS and must NOT be listed in columns
    (the SDK raises BadRequest if you request it explicitly).
    """
    rows = _rows(index.similarity_search(query_text=text, columns=["item_id", "search_text"], num_results=k))
    return [(r["item_id"], r["search_text"], float(r["score"])) for r in rows]
