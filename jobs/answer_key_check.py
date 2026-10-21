"""Asserts the v3 planted stories against live Delta and Lakebase state (geologic.harness.check)."""
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
from geologic.config import settings as S
from geologic.harness import check
from geologic.lakebase import apply_job_defaults, from_env

spark = SparkSession.builder.getOrCreate()
q = lambda sql: [r.asDict(recursive=True) for r in spark.sql(sql).collect()]
w = WorkspaceClient(); apply_job_defaults(w)


def lake(c, sql):
    cur = c.execute(sql)
    cols = [d.name for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


with from_env(w)() as c:
    fixes = lake(c, "SELECT fix_id, issue_id, asset_type, tier, state, patch_text, checks FROM fixes "
                    "WHERE epoch = (SELECT epoch FROM demo_state WHERE id = 1)")
    audits = lake(c, "SELECT exclusion_rule_id, enforcement_point, object_ref FROM audit_events")
state = {
    "kpis": q(f"SELECT * FROM {S.fq('v_kpis')}")[0],
    "issues": q(f"SELECT * FROM {S.fq('issues')}"),
    "fixes": fixes,
    "moments": q(f"SELECT * FROM {S.fq('moments')}"),
    "signals": q(f"SELECT s.signal_id, s.author, b.producer, s.quarantined, s.quarantine_rule_id "
                 f"FROM {S.fq('silver_signals')} s JOIN {S.fq('bronze_signals')} b USING (signal_id)"),
    "audits": audits,
    "public_signal_ids": {r["signal_id"] for r in q(f"SELECT signal_id FROM {S.fq('v_public_signals')}")},
    "personas": q(f"SELECT * FROM {S.fq('personas')}"),
}
failures = check(state)
for x in failures:
    print("FAIL", x)
if failures:
    raise SystemExit(1)
print("answer key: all v3 stories pass")
