"""Creates the VS endpoint and two Delta Sync indexes with managed embeddings, then waits until online."""
import sys
import os
import time

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from databricks.vector_search.client import VectorSearchClient
from geologic.config import settings as S

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


ensure(S.corpus_index, S.fq("web_corpus"), "doc_id", "body")
ensure(S.menu_index, S.fq("menu_search"), "item_id", "search_text")
print("vector search ready")
