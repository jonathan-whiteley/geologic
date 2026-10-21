"""Direct Vector Access rows and calls for the simulated web (sources_idx) and the prompt search (prompt_idx)."""
from __future__ import annotations
import json
import time

SOURCE_SCHEMA = {"doc_id": "string", "title": "string", "body": "string", "owner_class": "string", "domain": "string",
                 "embedding": "array<float>"}
PROMPT_SCHEMA = {"prompt_id": "string", "prompt_text": "string", "kind": "string", "cluster": "string", "embedding": "array<float>"}


def source_rows(docs, embed):
    vecs = embed([d["body"] or "" for d in docs])  # body only, as the v2 Delta Sync index embedded it
    return [{k: d.get(k) for k in SOURCE_SCHEMA if k != "embedding"} | {"embedding": v} for d, v in zip(docs, vecs)]


def prompt_rows(prompts, suggestions, embed):
    items = [(p["prompt_id"], p["prompt_text"], "tracked", p["cluster"]) for p in prompts]
    items += [(s["suggestion_id"], s["prompt_text"], "suggested", s.get("cluster")) for s in suggestions if s.get("status") == "suggested"]
    vecs = embed([t for _, t, _, _ in items])
    return [{"prompt_id": i, "prompt_text": t, "kind": k, "cluster": c, "embedding": v} for (i, t, k, c), v in zip(items, vecs)]


def ensure_direct_index(w, name, endpoint, pk, schema, dim):
    from databricks.sdk.errors import NotFound
    from databricks.sdk.service.vectorsearch import DirectAccessVectorIndexSpec, EmbeddingVectorColumn, VectorIndexType
    try:
        w.vector_search_indexes.get_index(name)
        return False
    except NotFound:
        w.vector_search_indexes.create_index(
            name=name, endpoint_name=endpoint, primary_key=pk, index_type=VectorIndexType.DIRECT_ACCESS,
            direct_access_index_spec=DirectAccessVectorIndexSpec(
                embedding_vector_columns=[EmbeddingVectorColumn(name="embedding", embedding_dimension=dim)],
                schema_json=json.dumps(schema)))
        return True


def wait_ready(w, name, timeout_s=1200):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        st = w.vector_search_indexes.get_index(name).status
        if st and st.ready:
            return
        time.sleep(15)
    raise TimeoutError(f"{name} not ready")


def upsert(w, index_name, rows, batch=100):
    for i in range(0, len(rows), batch):
        r = w.vector_search_indexes.upsert_data_vector_index(index_name=index_name, inputs_json=json.dumps(rows[i:i + batch]))
        status = getattr(getattr(r, "status", None), "value", str(getattr(r, "status", "")))
        if status != "SUCCESS":
            raise RuntimeError(f"upsert into {index_name} returned {status}")


def cosine_from_score(score) -> float:
    """Cosine similarity from a Direct Vector Access score. The index scores hits by L2 distance, score = 1 / (1 + d^2),
    and the Embedder stores unit vectors, so d^2 = 2 - 2 cos and cos = 1 - d^2 / 2 (clamped to [-1, 1])."""
    score = float(score or 0.0)
    if score <= 0.0:
        return -1.0
    return max(-1.0, min(1.0, 1.0 - (1.0 / score - 1.0) / 2.0))


def _rows(res) -> list[dict]:
    manifest, result = getattr(res, "manifest", None), getattr(res, "result", None)
    if manifest is None or result is None:
        return []
    cols = [c.name for c in manifest.columns or []]
    return [dict(zip(cols, r)) for r in result.data_array or []]


def query(w, index_name, columns, vector, k) -> list[dict]:
    """Nearest rows of a Direct Vector Access index to a unit query vector; "score" is the cosine similarity."""
    res = w.vector_search_indexes.query_index(index_name=index_name, columns=list(columns), query_vector=vector, num_results=k)
    return [r | {"score": cosine_from_score(r.get("score"))} for r in _rows(res)]


def delete(w, index_name, ids):
    """One key per call: with databricks-sdk 0.114 a multi-key delete (repeated query parameter) removes only one row."""
    for i in dict.fromkeys(ids):
        w.vector_search_indexes.delete_data_vector_index(index_name=index_name, primary_keys=[i])


def index_ids(w, index_name, pk, page=1000) -> list[str]:
    """Every primary key in a Direct Vector Access index (scan_index pages)."""
    out, last = [], None
    while True:
        r = w.vector_search_indexes.scan_index(index_name=index_name, last_primary_key=last, num_results=page)
        rows = getattr(r, "data", None) or []
        if not rows:
            return out
        for row in rows:
            v = next((e.value for e in row.fields or [] if e.key == pk), None)
            if v is not None and getattr(v, "string_value", None) is not None:
                out.append(v.string_value)
        last = getattr(r, "last_primary_key", None)
        if not last:
            return out


def prune(w, index_name, pk, keep) -> list[str]:
    """Deletes index rows whose primary key is not in keep; returns the deleted ids."""
    keep = set(keep)
    gone = sorted(i for i in dict.fromkeys(index_ids(w, index_name, pk)) if i not in keep)
    delete(w, index_name, gone)
    return gone
