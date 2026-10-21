"""Describes new signal images with a vision model and matches them to the menu via Vector Search."""
import sys
import os
from datetime import datetime, timezone

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
from geologic.clients import FmapiChat, menu_match, menu_candidates
from geologic.vision import describe_and_match, rerank_candidates

RERANK_K = 10      # top k from menu_idx shown to the reranker
MENU_ROWS = 64     # rank the whole menu (32 items) in one query so the text-resolved item's own score is known

spark = SparkSession.builder.getOrCreate()
# text_item_id: the item the pipeline resolved from the post's text (silver_signals is fresh: a pipeline update runs
# right before this task). A signal not yet described has no image match, so a confident menu_item_id is the text match.
todo = spark.sql(f"""SELECT r.signal_id, r.image_uri, s.menu_item_id AS text_item_id
  FROM {S.fq('silver_signals_raw')} r
  LEFT JOIN {S.fq('silver_signals')} s
    ON s.signal_id = r.signal_id AND s.image_match_score IS NULL AND s.resolution_confidence >= 0.9
  WHERE r.image_uri IS NOT NULL AND r.signal_id NOT IN (SELECT signal_id FROM {S.fq('image_descriptions')})""").collect()
chat = FmapiChat.from_workspace(WorkspaceClient())
idx = VectorSearchClient(disable_notice=True).get_index(S.vs_endpoint, S.menu_index)
out = []
for r in todo:
    with open(r["image_uri"], "rb") as f:
        d = describe_and_match(
            f.read(), chat, S.vision_endpoint,
            lambda t: menu_match(idx, t),
            candidates_fn=lambda t, tid=r["text_item_id"]: rerank_candidates(menu_candidates(idx, t, MENU_ROWS), RERANK_K, tid),
        )
    out.append((r["signal_id"], d["description"], d["matched_item_id"], d["match_score"], datetime.now(timezone.utc)))
if out:
    spark.createDataFrame(out, "signal_id STRING, description STRING, matched_item_id STRING, match_score DOUBLE, described_at TIMESTAMP") \
        .write.mode("append").saveAsTable(S.fq("image_descriptions"))
print(f"described {len(out)} images")
