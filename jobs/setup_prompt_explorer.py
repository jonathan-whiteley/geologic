"""Writes candidate prompts, monthly volume, prompt search source, doc brands; builds the prompt VS index."""
import sys, time
from datetime import date
sys.path.insert(0, "../src")
from pyspark.sql import SparkSession
from databricks.vector_search.client import VectorSearchClient
from geologic.config import settings as S
from geologic.datagen.reference import prompt_bank
from geologic.datagen.prompts_ext import prompt_candidates, monthly_volume
from geologic.brands import brand_for_doc

spark = SparkSession.builder.getOrCreate()
bank, cands = prompt_bank(), prompt_candidates()
spark.createDataFrame(cands).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq("prompt_candidates"))
end = date.today().replace(day=1)
vol = [r for p in bank + cands for r in monthly_volume(p, end)]
spark.createDataFrame(vol, "prompt_id STRING, month DATE, est_volume INT").write.mode("overwrite").saveAsTable(S.fq("question_volume_monthly"))
spark.createDataFrame([{"prompt_id": p["prompt_id"], "prompt_text": p["prompt_text"], "cluster": p["cluster"]} for p in bank + cands]) \
    .write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq("prompt_search"))
spark.sql(f"ALTER TABLE {S.fq('prompt_search')} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")
spark.sql(f"CREATE TABLE IF NOT EXISTS {S.fq('tracked_prompts')} (prompt_id STRING, tracked_by STRING, tracked_at TIMESTAMP)")
docs = [r.asDict() for r in spark.table(S.fq("web_corpus")).select("doc_id", "publisher", "is_official").collect()]
spark.createDataFrame([(d["doc_id"], brand_for_doc(d)) for d in docs if brand_for_doc(d)], "doc_id STRING, brand STRING") \
    .write.mode("overwrite").saveAsTable(S.fq("doc_brand"))

vsc = VectorSearchClient(disable_notice=True)
idx_name = S.fq("prompt_idx")
if idx_name not in [i["name"] for i in vsc.list_indexes(S.vs_endpoint).get("vector_indexes", [])]:
    vsc.create_delta_sync_index(endpoint_name=S.vs_endpoint, index_name=idx_name, source_table_name=S.fq("prompt_search"),
                                pipeline_type="TRIGGERED", primary_key="prompt_id", embedding_source_column="prompt_text",
                                embedding_model_endpoint_name=S.embedding_endpoint)
idx = vsc.get_index(S.vs_endpoint, idx_name)
for _ in range(90):
    if idx.describe().get("status", {}).get("ready"):
        break
    time.sleep(20)
print(f"prompt explorer ready: {len(bank)} tracked + {len(cands)} candidates")
