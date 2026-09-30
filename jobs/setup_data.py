"""Creates the schema, volume, and all reference tables. Safe to re-run (overwrites)."""
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
from geologic.config import settings as S
from geologic.datagen import reference as r, corpus as c
from geologic.exclusions import assert_persona_invariant

spark = SparkSession.builder.getOrCreate()
now = datetime.now(timezone.utc)
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {S.catalog}.{S.schema}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {S.fq('assets')}")


def write(name, rows, cdf=False):
    df = spark.createDataFrame(rows)
    df.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq(name))
    if cdf:
        spark.sql(f"ALTER TABLE {S.fq(name)} SET TBLPROPERTIES (delta.enableChangeDataFeed = true)")


assert_persona_invariant(r.personas())
pages = r.site_pages()
write("menu_items", r.menu_items())
write("deals", r.deals())
write("site_pages", pages)
write("site_pages_baseline", pages)
corpus = c.web_corpus(pages)
write("web_corpus", corpus, cdf=True)
write("web_corpus_baseline", corpus)
write("prompt_bank", r.prompt_bank())
write("demand_calendar", r.demand_calendar(now))
write("personas", r.personas())
write("exclusion_rules", r.exclusion_rules())
write("menu_search", [{"item_id": m["item_id"], "search_text": f"{m['name']}. {', '.join(m['aliases'])}. {m['category']}. {m['visual']}"} for m in r.menu_items()], cdf=True)

spark.sql(f"""CREATE TABLE IF NOT EXISTS {S.fq('bronze_signals')} (
  signal_id STRING, source_type STRING, payload STRING, image_uri STRING, ingested_at BIGINT, producer STRING)""")
spark.sql(f"""CREATE TABLE IF NOT EXISTS {S.fq('image_descriptions')} (
  signal_id STRING, description STRING, matched_item_id STRING, match_score DOUBLE, described_at TIMESTAMP)""")

# Weekly history before GEOlogic went live (Aug 3 to Sep 14); live weeks come from probe runs
hist = [(d, "Little Caesars", v) for d, v in zip(["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14"],
                                                 [0.29, 0.30, 0.28, 0.30, 0.33, 0.31, 0.35])]
hist += [(d, "Domino's", v) for d, v in zip(["2026-08-03", "2026-08-10", "2026-08-17", "2026-08-24", "2026-08-31", "2026-09-07", "2026-09-14"],
                                            [0.42, 0.41, 0.43, 0.42, 0.41, 0.42, 0.41])]
spark.createDataFrame(hist, "week_start STRING, brand STRING, answer_share DOUBLE") \
    .selectExpr("to_date(week_start) AS week_start", "brand", "answer_share") \
    .write.mode("overwrite").saveAsTable(S.fq("answer_share_weekly"))
print("setup_data complete")
