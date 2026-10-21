"""Writes the synthetic pre-launch weeks of Share of Model (answer_share_weekly) so they climb into the live baseline.

Reads the live Share of Model per brand from v_brand_share and the baseline run's start from probe_runs, then
overwrites answer_share_weekly with the seven Mondays before the baseline week (geologic.history). Re-run only when
the baseline changes; Reset does not touch history.
"""
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
from geologic.config import settings as S
from geologic.history import history_weeks, weekly_history

spark = SparkSession.builder.getOrCreate()
share = {r["brand"]: r["answer_share"] for r in spark.sql(f"SELECT brand, answer_share FROM {S.fq('v_brand_share')}").collect()}
base = spark.sql(f"""SELECT r.started_at FROM {S.fq('probe_runs')} r JOIN {S.fq('probe_state')} s
  ON s.id = 1 AND r.run_id = s.baseline_run_id WHERE r.status = 'ok'""").collect()
if not base or base[0]["started_at"] is None:
    raise SystemExit("no ok baseline run in probe_state.baseline_run_id; run the baseline probe first")
lce, dominos = share.get("Little Caesars"), share.get("Domino's")
if lce is None or dominos is None:
    raise SystemExit(f"v_brand_share has no live Share of Model for Little Caesars and Domino's: {share}")

rows = weekly_history(float(lce), float(dominos), history_weeks(base[0]["started_at"].date()))
(spark.createDataFrame(rows, "week_start DATE, brand STRING, answer_share DOUBLE")
 .write.mode("overwrite").saveAsTable(S.fq("answer_share_weekly")))
print(f"baseline {base[0]['started_at']}: live Little Caesars {lce:.3f}, Domino's {dominos:.3f}")
for week, brand, value in rows:
    print(f"  {week}  {brand:<15} {value:.3f}")
print(f"answer_share_weekly: {len(rows)} rows")
