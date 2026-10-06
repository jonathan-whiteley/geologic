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
from geologic.publish_flow import publish, DeltaStore, FRIENDLY_ERROR

ap = argparse.ArgumentParser(); ap.add_argument("--suggestion-id", required=True); a = ap.parse_args()
spark = SparkSession.builder.getOrCreate(); w = WorkspaceClient()
apply_job_defaults(w)

def _release(sid, err):
    """Best effort: never leave the row 'publishing' when the job dies outside publish(). The raw error
    goes to the job log; the card gets friendly text and Approve works again."""
    print("publish failed:", err)
    try:
        with from_env(w)() as c:
            c.execute("UPDATE suggestions SET state = 'pending_review', error = %s WHERE suggestion_id = %s AND state = 'publishing'",
                      (FRIENDLY_ERROR, sid))
            c.commit()
    except Exception as e2:
        print("could not release row:", e2)

try:
    rules = [r.asDict() for r in spark.table(S.fq("exclusion_rules")).collect()]
    with from_env(w)() as conn:
        cur = conn.execute("SELECT * FROM suggestions WHERE suggestion_id = %s", (a.suggestion_id,))
        cols = [d.name for d in cur.description]; row = cur.fetchone()
        if row is None:
            raise SystemExit(f"no suggestion {a.suggestion_id}")
        sg = dict(zip(cols, row))
        if sg["state"] != "publishing":  # reset restored it or a rerun already finished it: nothing to do
            print(a.suggestion_id, f"state is {sg['state']}, not publishing; exiting")
            raise SystemExit(0)
        sg["state"] = "approved"
        result = publish(sg, DeltaStore(spark, conn, w), rules, sg["epoch"])
except Exception as e:
    _release(a.suggestion_id, f"{type(e).__name__}: {e}")
    raise
print(a.suggestion_id, result)
if result in ("failed", "stale"):
    raise SystemExit(1)
