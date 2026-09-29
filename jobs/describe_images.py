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

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from databricks.vector_search.client import VectorSearchClient
from geologic.config import settings as S
from geologic.clients import FmapiChat, menu_match
from geologic.vision import describe_and_match

spark = SparkSession.builder.getOrCreate()
todo = spark.sql(f"""SELECT signal_id, image_uri FROM {S.fq('silver_signals_raw')}
  WHERE image_uri IS NOT NULL AND signal_id NOT IN (SELECT signal_id FROM {S.fq('image_descriptions')})""").collect()
chat = FmapiChat.from_workspace(WorkspaceClient())
idx = VectorSearchClient(disable_notice=True).get_index(S.vs_endpoint, S.menu_index)
out = []
for r in todo:
    with open(r["image_uri"], "rb") as f:
        d = describe_and_match(f.read(), chat, S.vision_endpoint, lambda t: menu_match(idx, t))
    out.append((r["signal_id"], d["description"], d["matched_item_id"], d["match_score"], datetime.now(timezone.utc)))
if out:
    spark.createDataFrame(out, "signal_id STRING, description STRING, matched_item_id STRING, match_score DOUBLE, described_at TIMESTAMP") \
        .write.mode("append").saveAsTable(S.fq("image_descriptions"))
print(f"described {len(out)} images")
