"""Publish job: the T0 batch (job parameter fix_ids, comma list). Fixes are claimed ('publishing') by the app first."""
import argparse
import os
import re
import sys
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
from geologic.config import settings as S
from geologic.lakebase import apply_job_defaults, from_env
from geologic.publish_flow import FRIENDLY_ERROR, DeltaJobStore, publish_batch

_FIX_ID = re.compile(r"^fx_[0-9a-f]{12}$")
ap = argparse.ArgumentParser(); ap.add_argument("--fix-ids", required=True); a = ap.parse_args()
ids = [i.strip() for i in a.fix_ids.split(",") if i.strip()]
bad = [i for i in ids if not _FIX_ID.match(i)]
if not ids or bad:
    raise SystemExit(f"--fix-ids needs fx_<12 hex> ids; got {a.fix_ids!r}")
spark = SparkSession.builder.getOrCreate(); w = WorkspaceClient()
apply_job_defaults(w)


def _release(err):
    """Best effort: never leave a listed row 'publishing' when the job dies outside publish_batch. The raw error goes to
    the job log; the cards get friendly text and Approve works again."""
    print("publish failed:", err)
    try:
        with from_env(w)() as c:
            c.execute("UPDATE fixes SET state = 'pending_review', error = %s WHERE fix_id = ANY(%s) AND state = 'publishing'",
                      (FRIENDLY_ERROR, ids))
            c.commit()
    except Exception as e2:
        print("could not release rows:", e2)


try:
    rules = [r.asDict() for r in spark.table(S.fq("exclusion_rules")).collect()]
    focus = {r["issue_id"]: (r["subject"], r["attribute"]) for r in spark.table(S.fq("issues")).collect()
             if r["subject"] and r["attribute"]}
    with from_env(w)() as conn:
        cur = conn.execute("SELECT * FROM fixes WHERE fix_id = ANY(%s)", (ids,))
        cols = [d.name for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        todo = []
        for r in rows:
            if r["state"] != "publishing":   # Reset restored it or a rerun already finished it: nothing to do
                print(r["fix_id"], f"state is {r['state']}, not publishing; skipping")
            else:
                todo.append(r)
        missing = sorted(set(ids) - {r["fix_id"] for r in rows})
        if missing:
            print("unknown fix ids:", missing)
        out = publish_batch(todo, DeltaJobStore(spark, conn, w), rules, now=datetime.now(timezone.utc),
                            focus_by_issue=focus) if todo else {}
except Exception as e:
    _release(f"{type(e).__name__}: {e}")
    raise
for fid, result in out.items():
    print(fid, result)
if any(v in ("failed", "stale") for v in out.values()):
    raise SystemExit(1)
