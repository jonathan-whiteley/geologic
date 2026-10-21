"""Vector Search for v3: the menu Delta Sync index (managed embeddings) and two Direct Vector Access indexes, the
simulated web (sources_idx, what the engines retrieve from) and the prompt search (prompt_idx). The endpoint is created
only if missing and never modified."""
import sys
import os
import time

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from geologic.config import settings as S
from geologic.clients import Embedder
from geologic import vectors as V

vsc = VectorSearchClient(disable_notice=True)
if S.vs_endpoint not in [e["name"] for e in vsc.list_endpoints().get("endpoints", [])]:
    vsc.create_endpoint_and_wait(name=S.vs_endpoint, endpoint_type="STANDARD")


def ensure(index, source, pk, col):
    existing = [i["name"] for i in vsc.list_indexes(S.vs_endpoint).get("vector_indexes", [])]
    if index not in existing:
        vsc.create_delta_sync_index(endpoint_name=S.vs_endpoint, index_name=index, source_table_name=source,
                                    pipeline_type="TRIGGERED", primary_key=pk, embedding_source_column=col,
                                    embedding_model_endpoint_name=S.embedding_endpoint)
    idx = vsc.get_index(S.vs_endpoint, index)
    idx.sync() if index in existing else None
    for _ in range(90):
        st = idx.describe().get("status", {})
        if st.get("ready"):
            return
        time.sleep(20)
    raise TimeoutError(f"{index} not ready: {st}")


ensure(S.menu_index, S.fq("menu_search"), "item_id", "search_text")

w = WorkspaceClient()
V.ensure_direct_index(w, S.sources_index, S.vs_endpoint, "doc_id", V.SOURCE_SCHEMA, S.embedding_dim)
V.ensure_direct_index(w, S.prompt_index, S.vs_endpoint, "prompt_id", V.PROMPT_SCHEMA, S.embedding_dim)
V.wait_ready(w, S.sources_index)
V.wait_ready(w, S.prompt_index)

spark = SparkSession.builder.getOrCreate()
embed = Embedder.from_workspace(w, S.embedding_endpoint).embed
docs = [r.asDict() for r in spark.table(S.fq("web_corpus")).select("doc_id", "title", "body", "owner_class", "domain").collect()]
prompts = [r.asDict() for r in spark.table(S.fq("prompts")).select("prompt_id", "prompt_text", "cluster").collect()]
suggestions = [r.asDict() for r in spark.table(S.fq("prompt_suggestions"))
               .select("suggestion_id", "prompt_text", "cluster", "status").collect()]
sources = V.source_rows(docs, embed)
prompt_rows = V.prompt_rows(prompts, suggestions, embed)
V.upsert(w, S.sources_index, sources)
V.upsert(w, S.prompt_index, prompt_rows)
print(f"sources_idx: {len(sources)} rows, prompt_idx: {len(prompt_rows)} rows")
