"""Builds gold_opportunities from probe gaps and signals. Safe to re-run (overwrite)."""
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
from geologic.opportunities import build

spark = SparkSession.builder.getOrCreate()
rows = lambda t: [r.asDict(recursive=True) for r in spark.table(S.fq(t)).collect()]
opps = build(rows("v_latest_responses"), rows("v_prompts"), rows("menu_items"), rows("demand_calendar"),
             rows("silver_signals"), datetime.now(timezone.utc), personas=rows("personas"))
schema = ("opp_id STRING, opp_type STRING, title STRING, item_id STRING, page_id STRING, persona_id STRING, visual_sourced BOOLEAN, "
          "resolution_confidence DOUBLE, prompt_ids ARRAY<STRING>, signal_ids ARRAY<STRING>, cluster STRING, gap_severity DOUBLE, "
          "expected_lift_low DOUBLE, expected_lift_high DOUBLE, question_volume DOUBLE, window_name STRING, window_expires_at TIMESTAMP, reasoning STRING, "
          "assets ARRAY<STRING>, status STRING, rank INT")
spark.createDataFrame(opps, schema).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(S.fq("gold_opportunities"))
print(f"{len(opps)} opportunities")
