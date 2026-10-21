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


def delete(w, index_name, ids):
    ids = list(ids)
    if ids:
        w.vector_search_indexes.delete_data_vector_index(index_name=index_name, primary_keys=ids)
