"""Nightly consistency: re-embed every web_corpus row into the Direct Vector Access sources index. Ids that leave
web_corpus are deleted from the index by Reset, the only path that removes pages."""
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from geologic import jobargs; jobargs.apply()

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic import vectors as V
from geologic.clients import Embedder
from geologic.config import settings as S

spark = SparkSession.builder.getOrCreate(); w = WorkspaceClient()
docs = [r.asDict() for r in spark.table(S.fq("web_corpus")).collect()]
V.upsert(w, S.sources_index, V.source_rows(docs, Embedder.from_workspace(w, S.embedding_endpoint).embed))
print(f"re-embedded {len(docs)} web_corpus rows into {S.sources_index}")
