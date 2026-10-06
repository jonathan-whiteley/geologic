"""Publish job: applies one approved suggestion (job parameter suggestion_id). Keep next to run_probe.py."""
import argparse
import os
import sys

# Serverless spark_python_task exec does not set __file__; cwd is the script's workspace dir.
try:
    _src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
except NameError:
    _src = os.path.abspath(os.path.join(os.getcwd(), "..", "src"))
sys.path.insert(0, _src)

from pyspark.sql import SparkSession
from databricks.sdk import WorkspaceClient
from geologic.config import settings as S
from geologic.lakebase import from_env, apply_job_defaults
from geologic.publish_flow import publish, DeltaStore

ap = argparse.ArgumentParser(); ap.add_argument("--suggestion-id", required=True); a = ap.parse_args()
spark = SparkSession.builder.getOrCreate(); w = WorkspaceClient()
apply_job_defaults(w)
rules = [r.asDict() for r in spark.table(S.fq("exclusion_rules")).collect()]
with from_env(w)() as conn:
    cur = conn.execute("SELECT * FROM suggestions WHERE suggestion_id = %s", (a.suggestion_id,))
    cols = [d.name for d in cur.description]; row = cur.fetchone()
    if row is None:
        raise SystemExit(f"no suggestion {a.suggestion_id}")
    sg = dict(zip(cols, row))
    sg["state"] = "approved" if sg["state"] == "publishing" else sg["state"]
    result = publish(sg, DeltaStore(spark, conn, w), rules, sg["epoch"])
print(a.suggestion_id, result)
if result == "failed":
    raise SystemExit(1)
