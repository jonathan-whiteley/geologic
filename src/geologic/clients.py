"""Adapters from Databricks services to the core protocols. Kept thin so the core stays testable."""
from __future__ import annotations
from geologic.probe.engine import Doc


class FmapiChat:
    def __init__(self, openai_client):
        self._c = openai_client
        self._no_temperature = set()  # endpoints that only accept the default temperature (Claude 5.5, GPT-5.5, Gemini 3.8)

    @classmethod
    def from_workspace(cls, w):
        return cls(w.serving_endpoints.get_open_ai_client())

    def complete(self, endpoint, messages, max_tokens=600, usage_context=None):
        kw = {"extra_body": {"usage_context": usage_context}} if usage_context else {}
        if endpoint not in self._no_temperature:
            try:
                return self._text(self._c.chat.completions.create(model=endpoint, messages=messages, max_tokens=max_tokens,
                                                                  temperature=0.2, **kw))
            except Exception as e:
                if "temperature" not in str(e):
                    raise
                self._no_temperature.add(endpoint)
        return self._text(self._c.chat.completions.create(model=endpoint, messages=messages, max_tokens=max_tokens, **kw))

    @staticmethod
    def _text(r):
        content = r.choices[0].message.content
        if isinstance(content, list):  # reasoning models return typed parts
            return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
        return content or ""


def _rows(res):
    cols = [c["name"] for c in res["manifest"]["columns"]]
    return [dict(zip(cols, r)) for r in res.get("result", {}).get("data_array", []) or []]


class Embedder:
    """Query and row embeddings from a Foundation Model API embeddings endpoint (databricks-gte-large-en, 1024 dims)."""

    def __init__(self, openai_client, endpoint, batch=16):
        self._c, self.endpoint, self.batch = openai_client, endpoint, batch

    @classmethod
    def from_workspace(cls, w, endpoint):
        return cls(w.serving_endpoints.get_open_ai_client(), endpoint)

    def embed(self, texts) -> list[list[float]]:
        texts, out = list(texts), []
        for i in range(0, len(texts), self.batch):
            r = self._c.embeddings.create(model=self.endpoint, input=texts[i:i + self.batch])
            out += [list(d.embedding) for d in sorted(r.data, key=lambda d: getattr(d, "index", 0) or 0)]
        return out


def _sdk_rows(res) -> list[dict]:
    """Rows of a WorkspaceClient vector_search_indexes.query_index response (score is appended by Vector Search)."""
    manifest, result = getattr(res, "manifest", None), getattr(res, "result", None)
    if manifest is None or result is None:
        return []
    cols = [c.name for c in manifest.columns or []]
    return [dict(zip(cols, r)) for r in result.data_array or []]


class DvaRetriever:
    """Engine retrieval from the Direct Vector Access sources index: embeds the prompt, then queries by vector."""

    def __init__(self, w, index_name, embedder, columns=("doc_id", "title", "body", "owner_class")):
        self.w, self.index_name, self.embedder, self.columns = w, index_name, embedder, list(columns)

    def search(self, query, k) -> list[Doc]:
        vec = self.embedder.embed([query])[0]
        res = self.w.vector_search_indexes.query_index(index_name=self.index_name, columns=self.columns, query_vector=vec,
                                                       num_results=k)
        return [Doc(r["doc_id"], r.get("title") or "", r.get("body") or "", r.get("owner_class") == "Owned")
                for r in _sdk_rows(res)]


class PromptIndex:
    """Nearest tracked or suggested prompts from the Direct Vector Access prompt index."""

    COLUMNS = ["prompt_id", "prompt_text", "kind", "cluster"]

    def __init__(self, w, index_name, embedder):
        self.w, self.index_name, self.embedder = w, index_name, embedder

    def nearest(self, text, k=3) -> list[dict]:
        vec = self.embedder.embed([text])[0]
        res = self.w.vector_search_indexes.query_index(index_name=self.index_name, columns=list(self.COLUMNS),
                                                       query_vector=vec, num_results=k)
        return [{"id": r["prompt_id"], "prompt_text": r["prompt_text"], "kind": r["kind"], "cluster": r["cluster"],
                 "score": float(r["score"])} for r in _sdk_rows(res)]


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
